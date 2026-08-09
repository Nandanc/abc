"""Backtest engine for Golden Cross / Death Cross strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .config import (
    BROKERAGE_PCT,
    INITIAL_CAPITAL,
    SLIPPAGE_PCT,
    STT_PCT,
)
from .metrics import compute_metrics, MetricsResult
from .strategy import (
    extract_trades_from_signals,
    generate_risk_managed_signals,
    generate_signals,
)

logger = logging.getLogger(__name__)


@dataclass
class StockBacktestResult:
    symbol: str
    signals_df: pd.DataFrame
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: MetricsResult
    initial_capital: float


@dataclass
class PortfolioBacktestResult:
    equity_curve: pd.Series
    metrics: MetricsResult
    stock_results: List[StockBacktestResult] = field(default_factory=list)
    aggregate_trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    backtest_start: Optional[str] = None
    backtest_end: Optional[str] = None


def _transaction_cost_pct(is_buy: bool) -> float:
    cost = BROKERAGE_PCT + SLIPPAGE_PCT
    if not is_buy:
        cost += STT_PCT
    return cost


def backtest_single_stock(
    symbol: str,
    df: pd.DataFrame,
    initial_capital: float,
    use_risk_management: bool = True,
) -> Optional[StockBacktestResult]:
    """Run backtest with optional stop-loss / trailing-stop / take-profit exits."""
    if use_risk_management:
        signals = generate_risk_managed_signals(df)
        trades = extract_trades_from_signals(signals)
    else:
        signals = generate_signals(df)
        from .strategy import extract_trades as extract_legacy_trades

        trades = extract_legacy_trades(df)

    if signals["SMA_long"].isna().all():
        return None

    cash = initial_capital
    shares = 0.0
    equity_values = []

    if use_risk_management:
        in_position = False
        for date, row in signals.iterrows():
            if row.get("entry_signal", False) and not in_position:
                buy_price = float(row["Close"]) * (1 + _transaction_cost_pct(True))
                shares = cash / buy_price
                cash = 0.0
                in_position = True
            elif row.get("exit_signal", False) and in_position:
                sell_raw = (
                    float(row["trade_exit_price"])
                    if pd.notna(row.get("trade_exit_price"))
                    else float(row["Close"])
                )
                sell_price = sell_raw * (1 - _transaction_cost_pct(False))
                cash = shares * sell_price
                shares = 0.0
                in_position = False

            price = float(row["Close"])
            equity_values.append(cash + shares * price)
    else:
        prev_position = 0
        for date, row in signals.iterrows():
            price = float(row["Close"])
            position = int(row["position"])

            if position == 1 and prev_position == 0 and row["golden_cross"]:
                buy_price = price * (1 + _transaction_cost_pct(True))
                shares = cash / buy_price
                cash = 0.0
            elif position == 0 and prev_position == 1 and row["death_cross"]:
                sell_price = price * (1 - _transaction_cost_pct(False))
                cash = shares * sell_price
                shares = 0.0

            equity_values.append(cash + shares * price)
            prev_position = position

    equity_curve = pd.Series(equity_values, index=signals.index, name=symbol)

    if not trades.empty:
        trades = trades.copy()
        trades["symbol"] = symbol
        round_trip_cost = _transaction_cost_pct(True) + _transaction_cost_pct(False)
        trades["return_pct_net"] = trades["return_pct"] - round_trip_cost

    daily_returns = equity_curve.pct_change().fillna(0)
    metrics = compute_metrics(equity_curve, daily_returns, trades)

    return StockBacktestResult(
        symbol=symbol,
        signals_df=signals,
        equity_curve=equity_curve,
        trades=trades,
        metrics=metrics,
        initial_capital=initial_capital,
    )


def backtest_portfolio(
    price_data: Dict[str, pd.DataFrame],
    initial_capital: float = INITIAL_CAPITAL,
    use_risk_management: bool = True,
) -> PortfolioBacktestResult:
    """
    Backtest each Nifty 500 stock with equal capital allocation.
    Portfolio equity = sum of individual stock equity curves.
    """
    n = len(price_data)
    if n == 0:
        raise ValueError("No price data provided")

    capital_per_stock = initial_capital / n
    stock_results: List[StockBacktestResult] = []

    for symbol, df in price_data.items():
        result = backtest_single_stock(
            symbol, df, capital_per_stock, use_risk_management=use_risk_management
        )
        if result is not None:
            stock_results.append(result)

    if not stock_results:
        raise ValueError("No successful backtests")

    equity_df = pd.DataFrame({r.symbol: r.equity_curve for r in stock_results})
    equity_df = equity_df.sort_index().ffill().bfill()

    portfolio_equity = equity_df.sum(axis=1)
    portfolio_equity.name = "Portfolio"

    daily_returns = portfolio_equity.pct_change().fillna(0)

    all_trades = pd.concat(
        [r.trades for r in stock_results if not r.trades.empty],
        ignore_index=True,
    )

    portfolio_metrics = compute_metrics(portfolio_equity, daily_returns, all_trades)

    return PortfolioBacktestResult(
        equity_curve=portfolio_equity,
        metrics=portfolio_metrics,
        stock_results=stock_results,
        aggregate_trades=all_trades,
    )


def apply_backtest_window(
    result: PortfolioBacktestResult,
    backtest_start: str,
    backtest_end: Optional[str] = None,
) -> PortfolioBacktestResult:
    """Restrict metrics, equity curve, and trades to the requested date window."""
    start_ts = pd.Timestamp(backtest_start)
    end_ts = pd.Timestamp(backtest_end) if backtest_end else None

    eq = result.equity_curve[result.equity_curve.index >= start_ts]
    if end_ts is not None:
        eq = eq[eq.index <= end_ts]
    if len(eq) < 2:
        return result

    trades = result.aggregate_trades
    if not trades.empty and "entry_date" in trades.columns:
        entry_dates = pd.to_datetime(trades["entry_date"])
        mask = entry_dates >= start_ts
        if end_ts is not None:
            mask &= entry_dates <= end_ts
        trades = trades[mask]

    daily_returns = eq.pct_change().fillna(0)
    portfolio_metrics = compute_metrics(eq, daily_returns, trades)

    new_stock_results: List[StockBacktestResult] = []
    for r in result.stock_results:
        stock_eq = r.equity_curve[r.equity_curve.index >= start_ts]
        if end_ts is not None:
            stock_eq = stock_eq[stock_eq.index <= end_ts]
        if len(stock_eq) < 2:
            continue

        stock_trades = r.trades
        if not stock_trades.empty and "entry_date" in stock_trades.columns:
            entry_dates = pd.to_datetime(stock_trades["entry_date"])
            mask = entry_dates >= start_ts
            if end_ts is not None:
                mask &= entry_dates <= end_ts
            stock_trades = stock_trades[mask]

        stock_metrics = compute_metrics(
            stock_eq,
            stock_eq.pct_change().fillna(0),
            stock_trades,
        )
        new_stock_results.append(
            StockBacktestResult(
                symbol=r.symbol,
                signals_df=r.signals_df,
                equity_curve=stock_eq,
                trades=stock_trades,
                metrics=stock_metrics,
                initial_capital=float(stock_eq.iloc[0]),
            )
        )

    return PortfolioBacktestResult(
        equity_curve=eq,
        metrics=portfolio_metrics,
        stock_results=new_stock_results,
        aggregate_trades=trades,
        backtest_start=backtest_start,
        backtest_end=backtest_end or str(eq.index[-1].date()),
    )


def summarize_exit_reasons(trades: pd.DataFrame) -> pd.DataFrame:
    """Count how often each exit type fired."""
    if trades.empty or "exit_reason" not in trades.columns:
        return pd.DataFrame()
    summary = trades.groupby("exit_reason").agg(
        count=("return_pct", "count"),
        avg_return_pct=("return_pct", lambda x: x.mean() * 100),
        avg_loss_pct=(
            "return_pct",
            lambda x: x[x < 0].mean() * 100 if (x < 0).any() else 0,
        ),
    ).reset_index()
    return summary.round(2)


def summarize_stock_metrics(stock_results: List[StockBacktestResult]) -> pd.DataFrame:
    """Per-stock metrics summary table."""
    rows = []
    for r in stock_results:
        m = r.metrics
        rows.append(
            {
                "Symbol": r.symbol,
                "Total Return %": round(m.total_return_pct, 2),
                "CAGR %": round(m.cagr_pct, 2),
                "Max Drawdown %": round(m.max_drawdown_pct, 2),
                "Sharpe": round(m.sharpe_ratio, 2),
                "Win Rate %": round(m.win_rate_pct, 2),
                "Trades": m.num_trades,
                "Profit Factor": round(m.profit_factor, 2) if m.profit_factor else None,
            }
        )
    return pd.DataFrame(rows).sort_values("Total Return %", ascending=False)
