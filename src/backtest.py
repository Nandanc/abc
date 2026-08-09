"""Backtest engine for Golden Cross / Death Cross strategy."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import (
    BROKERAGE_PCT,
    INITIAL_CAPITAL,
    SLIPPAGE_PCT,
    STT_PCT,
)
from .metrics import compute_metrics, MetricsResult
from .strategy import extract_trades, generate_signals

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


def _transaction_cost_pct(is_buy: bool) -> float:
    cost = BROKERAGE_PCT + SLIPPAGE_PCT
    if not is_buy:
        cost += STT_PCT
    return cost


def backtest_single_stock(
    symbol: str,
    df: pd.DataFrame,
    initial_capital: float,
) -> Optional[StockBacktestResult]:
    """Run backtest on one stock with position sizing = full allocated capital."""
    signals = generate_signals(df)
    if signals["SMA_long"].isna().all():
        return None

    cash = initial_capital
    shares = 0.0
    equity_values = []

    prev_position = 0
    for date, row in signals.iterrows():
        price = row["Close"]
        position = int(row["position"])

        if position == 1 and prev_position == 0 and row["golden_cross"]:
            buy_price = price * (1 + _transaction_cost_pct(True))
            shares = cash / buy_price
            cash = 0.0
        elif position == 0 and prev_position == 1 and row["death_cross"]:
            sell_price = price * (1 - _transaction_cost_pct(False))
            cash = shares * sell_price
            shares = 0.0

        equity = cash + shares * price
        equity_values.append(equity)
        prev_position = position

    equity_curve = pd.Series(equity_values, index=signals.index, name=symbol)
    trades = extract_trades(signals)
    if not trades.empty:
        trades["symbol"] = symbol
        # Apply transaction costs to trade returns
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
        result = backtest_single_stock(symbol, df, capital_per_stock)
        if result is not None:
            stock_results.append(result)

    if not stock_results:
        raise ValueError("No successful backtests")

    # Align all equity curves on common dates
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
