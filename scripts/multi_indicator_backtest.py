#!/usr/bin/env python3
"""
Standalone multi-indicator backtest report (does NOT modify existing strategy code).

Indicators used for entry/exit confirmation:
  - Golden Cross / Death Cross (50/200 SMA)
  - Bollinger Bands (20, 2σ)
  - RSI (14)
  - MACD (12, 26, 9)
  - Fibonacci retracement levels (from recent swing)
  - Volume (vs 20-day average)

Risk metrics reported: Calmar, Sortino, Sharpe, Max Drawdown, Profit Factor, etc.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tabulate import tabulate

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import (  # noqa: E402
    BROKERAGE_PCT,
    DATA_DIR,
    INITIAL_CAPITAL,
    OUTPUT_DIR,
    SLIPPAGE_PCT,
    STT_PCT,
    get_backtest_period,
)
from src.data_loader import download_stock_data, load_nifty500_symbols  # noqa: E402
from src.metrics import compute_metrics  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("multi_indicator")

STOP_LOSS = 0.08
TAKE_PROFIT = 0.40


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]
    volume = out["Volume"] if "Volume" in out.columns else pd.Series(0, index=out.index)

    # Moving averages + golden/death cross base
    out["SMA50"] = close.rolling(50).mean()
    out["SMA200"] = close.rolling(200).mean()

    # Bollinger Bands (20, 2)
    mid = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["BB_mid"] = mid
    out["BB_upper"] = mid + 2 * std
    out["BB_lower"] = mid - 2 * std
    out["BB_pct"] = (close - out["BB_lower"]) / (out["BB_upper"] - out["BB_lower"])

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_hist"] = out["MACD"] - out["MACD_signal"]

    # Volume vs 20-day average
    out["Vol_SMA20"] = volume.rolling(20).mean()
    out["Vol_ratio"] = volume / out["Vol_SMA20"].replace(0, np.nan)

    # Fibonacci levels from 60-day swing high/low
    swing_high = close.rolling(60).max()
    swing_low = close.rolling(60).min()
    rng = swing_high - swing_low
    out["Fib_0"] = swing_high
    out["Fib_236"] = swing_high - 0.236 * rng
    out["Fib_382"] = swing_high - 0.382 * rng
    out["Fib_500"] = swing_high - 0.500 * rng
    out["Fib_618"] = swing_high - 0.618 * rng
    out["Fib_1"] = swing_low
    # Near Fibonacci support (price within 1.5% of 38.2% / 50% / 61.8%)
    near_fib = (
        ((close - out["Fib_382"]).abs() / close < 0.015)
        | ((close - out["Fib_500"]).abs() / close < 0.015)
        | ((close - out["Fib_618"]).abs() / close < 0.015)
        | ((close >= out["Fib_618"]) & (close <= out["Fib_382"]))
    )
    out["near_fib_support"] = near_fib.fillna(False)

    return out


def simulate_stock(df: pd.DataFrame, capital: float) -> tuple[pd.Series, pd.DataFrame]:
    """
    ENTRY (all must be true):
      1. Golden cross OR (price above SMA50 & SMA200 and SMA50 > SMA200)
      2. RSI between 40 and 65 (not overbought, not deeply oversold)
      3. MACD > signal (bullish momentum)
      4. Close above BB mid OR bouncing from lower band (BB_pct < 0.3 then rising)
      5. Volume ratio >= 1.0 (above-average volume)
      6. Near Fibonacci support OR close above Fib 50%

    EXIT (any):
      - Stop loss -8%
      - Take profit +40%
      - Death cross
      - RSI > 75 (overbought)
      - MACD crosses below signal
      - Close closes below BB mid after being above (weakness)
    """
    data = add_indicators(df)
    cash = capital
    shares = 0.0
    in_pos = False
    entry = 0.0
    equity = []
    trades = []
    entry_date = None
    entry_flags = {}

    prev = None
    for date, row in data.iterrows():
        if prev is None or pd.isna(row["SMA200"]) or pd.isna(row["RSI"]):
            equity.append(cash + shares * float(row["Close"]))
            prev = row
            continue

        close = float(row["Close"])
        low = float(row["Low"])
        high = float(row["High"])

        golden = row["SMA50"] > row["SMA200"] and prev["SMA50"] <= prev["SMA200"]
        death = row["SMA50"] < row["SMA200"] and prev["SMA50"] >= prev["SMA200"]
        uptrend = row["SMA50"] > row["SMA200"] and close > row["SMA50"]

        rsi_ok = 40 <= row["RSI"] <= 65
        macd_bull = row["MACD"] > row["MACD_signal"]
        macd_bear_cross = row["MACD"] < row["MACD_signal"] and prev["MACD"] >= prev["MACD_signal"]
        bb_ok = (row["BB_pct"] >= 0.3 and close >= row["BB_mid"]) or (row["BB_pct"] <= 0.25)
        vol_ok = pd.notna(row["Vol_ratio"]) and row["Vol_ratio"] >= 1.0
        fib_ok = bool(row["near_fib_support"]) or (close >= row["Fib_500"] if pd.notna(row["Fib_500"]) else False)

        if not in_pos:
            entry_ok = (golden or uptrend) and rsi_ok and macd_bull and bb_ok and vol_ok and fib_ok
            # Prefer true golden-cross days, but allow trend continuation entries once per setup
            if entry_ok and (golden or (uptrend and close > prev["Close"])):
                # Enter only on golden cross OR first confirmation day after pullback near Fib
                if golden or bool(row["near_fib_support"]):
                    buy = close * (1 + BROKERAGE_PCT + SLIPPAGE_PCT)
                    shares = cash / buy
                    cash = 0.0
                    in_pos = True
                    entry = close
                    entry_date = date
                    entry_flags = {
                        "rsi": round(float(row["RSI"]), 1),
                        "macd_hist": round(float(row["MACD_hist"]), 4),
                        "bb_pct": round(float(row["BB_pct"]), 2) if pd.notna(row["BB_pct"]) else None,
                        "vol_ratio": round(float(row["Vol_ratio"]), 2) if pd.notna(row["Vol_ratio"]) else None,
                        "near_fib": bool(row["near_fib_support"]),
                        "entry_type": "golden_cross" if golden else "fib_pullback",
                    }
        else:
            stop = entry * (1 - STOP_LOSS)
            target = entry * (1 + TAKE_PROFIT)
            exit_reason = None
            exit_px = close

            if low <= stop:
                exit_reason, exit_px = "stop_loss", stop
            elif high >= target:
                exit_reason, exit_px = "take_profit", target
            elif death:
                exit_reason = "death_cross"
            elif row["RSI"] > 75:
                exit_reason = "rsi_overbought"
            elif macd_bear_cross:
                exit_reason = "macd_bear_cross"
            elif close < row["BB_mid"] and prev["Close"] >= prev["BB_mid"]:
                exit_reason = "bb_mid_break"

            if exit_reason:
                sell = exit_px * (1 - BROKERAGE_PCT - SLIPPAGE_PCT - STT_PCT)
                cash = shares * sell
                shares = 0.0
                in_pos = False
                pnl = (exit_px - entry) / entry
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "entry_price": entry,
                        "exit_price": exit_px,
                        "return_pct": pnl,
                        "return_pct_net": pnl - (BROKERAGE_PCT + SLIPPAGE_PCT) * 2 - STT_PCT,
                        "exit_reason": exit_reason,
                        "holding_days": (date - entry_date).days,
                        **{f"entry_{k}": v for k, v in entry_flags.items()},
                    }
                )
                entry = 0.0
                entry_date = None

        equity.append(cash + shares * close)
        prev = row

    eq = pd.Series(equity, index=data.index, name="equity")
    return eq, pd.DataFrame(trades)


def run(limit: int | None = None) -> Path:
    download_start, backtest_start, backtest_end = get_backtest_period(10)
    symbols = load_nifty500_symbols(DATA_DIR / "nifty500_symbols.csv")
    if limit:
        symbols = symbols[:limit]

    logger.info("Downloading data from %s ...", download_start)
    price_data = download_stock_data(symbols, start=download_start)
    logger.info("Loaded %d stocks. Running multi-indicator backtest...", len(price_data))

    capital_each = INITIAL_CAPITAL / max(len(price_data), 1)
    equity_map = {}
    all_trades = []

    for i, (sym, df) in enumerate(price_data.items(), 1):
        if i % 50 == 0:
            logger.info("  processed %d / %d", i, len(price_data))
        eq, trades = simulate_stock(df, capital_each)
        equity_map[sym] = eq
        if not trades.empty:
            trades["symbol"] = sym
            all_trades.append(trades)

    equity_df = pd.DataFrame(equity_map).sort_index().ffill().bfill()
    start_ts = pd.Timestamp(backtest_start)
    end_ts = pd.Timestamp(backtest_end)
    equity_df = equity_df[(equity_df.index >= start_ts) & (equity_df.index <= end_ts)]
    portfolio = equity_df.sum(axis=1)
    portfolio.name = "Portfolio"

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if not trades_df.empty:
        trades_df = trades_df[
            (pd.to_datetime(trades_df["entry_date"]) >= start_ts)
            & (pd.to_datetime(trades_df["entry_date"]) <= end_ts)
        ]

    metrics = compute_metrics(portfolio, portfolio.pct_change().fillna(0), trades_df)

    # Charts + report
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_path = OUTPUT_DIR / f"multi_indicator_equity_{ts}.png"
    report_path = OUTPUT_DIR / f"multi_indicator_report_{ts}.md"
    trades_path = OUTPUT_DIR / f"multi_indicator_trades_{ts}.csv"

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})
    axes[0].plot(portfolio.index, portfolio.values, color="#1B4F72", lw=1.5)
    axes[0].set_title(
        f"Multi-Indicator Strategy Equity (BB + RSI + MACD + Fib + Volume) | {backtest_start} to {backtest_end}"
    )
    axes[0].set_ylabel("Portfolio Value (INR)")
    dd = (portfolio - portfolio.cummax()) / portfolio.cummax() * 100
    axes[1].fill_between(dd.index, dd.values, 0, color="#C0392B", alpha=0.6)
    axes[1].set_ylabel("Drawdown %")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.tight_layout()
    fig.savefig(chart_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    if not trades_df.empty:
        trades_df.to_csv(trades_path, index=False)

    exit_summary = ""
    if not trades_df.empty and "exit_reason" in trades_df.columns:
        es = (
            trades_df.groupby("exit_reason")
            .agg(count=("return_pct", "count"), avg_return_pct=("return_pct", lambda x: x.mean() * 100))
            .reset_index()
            .round(2)
        )
        exit_summary = tabulate(es.values, headers=es.columns, tablefmt="pipe", floatfmt=".2f")

    metrics_table = [
        ["Total Return (%)", f"{metrics.total_return_pct:.2f}"],
        ["CAGR (%)", f"{metrics.cagr_pct:.2f}"],
        ["Max Drawdown (%)", f"{metrics.max_drawdown_pct:.2f}"],
        ["Sharpe Ratio", f"{metrics.sharpe_ratio:.2f}"],
        ["Sortino Ratio", f"{metrics.sortino_ratio:.2f}"],
        ["Calmar Ratio", f"{metrics.calmar_ratio:.2f}"],
        ["Annual Volatility (%)", f"{metrics.volatility_annual_pct:.2f}"],
        ["Win Rate (%)", f"{metrics.win_rate_pct:.2f}"],
        ["Number of Trades", metrics.num_trades],
        ["Avg Trade Return (%)", f"{metrics.avg_trade_return_pct:.2f}"],
        ["Avg Win (%)", f"{metrics.avg_win_pct:.2f}"],
        ["Avg Loss (%)", f"{metrics.avg_loss_pct:.2f}"],
        ["Profit Factor", f"{metrics.profit_factor:.2f}"],
        ["Expectancy (%)", f"{metrics.expectancy_pct:.2f}"],
        ["Best Trade (%)", f"{metrics.best_trade_pct:.2f}"],
        ["Worst Trade (%)", f"{metrics.worst_trade_pct:.2f}"],
        ["Avg Holding (days)", f"{metrics.avg_holding_days:.1f}"],
        ["Recovery Factor", f"{metrics.recovery_factor:.2f}"],
        ["Ulcer Index", f"{metrics.ulcer_index:.2f}"],
    ]

    start_val = float(portfolio.iloc[0])
    end_val = float(portfolio.iloc[-1])
    profit = end_val - start_val

    report = f"""# Multi-Indicator Backtest Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Strategy (no change to existing golden-cross code — standalone run)

Base trend: **Golden Cross / Death Cross (50/200)**  
Confirmation filters added for this report:

| Indicator | Role |
|-----------|------|
| **Bollinger Bands (20, 2σ)** | Enter near mid/lower band strength; exit on mid-band break |
| **RSI (14)** | Enter only if RSI 40–65; exit if RSI > 75 |
| **MACD (12, 26, 9)** | Enter when MACD > signal; exit on bearish MACD cross |
| **Fibonacci (60-day swing)** | Prefer entries near 38.2% / 50% / 61.8% support |
| **Volume** | Require volume ≥ 20-day average |

Risk exits: **−8% stop loss**, **+40% take profit**, plus death cross.

## Period & Capital

- **Backtest Period:** {backtest_start} to {backtest_end} (10 years)
- **Universe:** Nifty 500 ({len(price_data)} stocks with data)
- **Initial Capital:** ₹{INITIAL_CAPITAL:,.0f}
- **Ending Capital:** ₹{end_val:,.0f}
- **Net P&L:** ₹{profit:,.0f} ({metrics.total_return_pct:.2f}%)

## Performance Summary (includes Calmar & Sortino)

{tabulate(metrics_table, headers=["Metric", "Value"], tablefmt="pipe")}

## Simple P&L

| | Amount |
|---|--------|
| Start | ₹{start_val:,.0f} |
| End | ₹{end_val:,.0f} |
| Profit / Loss | ₹{profit:,.0f} |
| CAGR | {metrics.cagr_pct:.2f}% |
| Max Drawdown | {metrics.max_drawdown_pct:.2f}% |
| **Sortino** | **{metrics.sortino_ratio:.2f}** |
| **Calmar** | **{metrics.calmar_ratio:.2f}** |
| Profit Factor | {metrics.profit_factor:.2f} |

## Exit Reasons

{exit_summary if exit_summary else "_No completed trades_"}

## Charts

![Equity Curve]({chart_path.name})

## Files

- `{chart_path.name}` — equity + drawdown
- `{trades_path.name if not trades_df.empty else "n/a"}` — all trades with indicator entry tags
- `{report_path.name}` — this report

## How to read Calmar & Sortino

- **Sortino**: return vs *downside* volatility only (higher = better risk-adjusted return)
- **Calmar**: CAGR ÷ Max Drawdown (higher = more return per unit of worst drawdown)

## Disclaimer

Educational backtest only. Past performance does not guarantee future results. Not financial advice.
"""
    report_path.write_text(report)
    logger.info("Report saved: %s", report_path)

    print("\n" + "=" * 64)
    print("  MULTI-INDICATOR BACKTEST (BB + RSI + MACD + Fib + Volume)")
    print("=" * 64)
    print(f"  Period:         {backtest_start} → {backtest_end}")
    print(f"  Stocks:         {len(price_data)}")
    print(f"  Start capital:  ₹{start_val:,.0f}")
    print(f"  End capital:    ₹{end_val:,.0f}")
    print(f"  Net P&L:        ₹{profit:,.0f} ({metrics.total_return_pct:.2f}%)")
    print(f"  CAGR:           {metrics.cagr_pct:.2f}%")
    print(f"  Max Drawdown:   {metrics.max_drawdown_pct:.2f}%")
    print(f"  Sharpe:         {metrics.sharpe_ratio:.2f}")
    print(f"  Sortino:        {metrics.sortino_ratio:.2f}")
    print(f"  Calmar:         {metrics.calmar_ratio:.2f}")
    print(f"  Win Rate:       {metrics.win_rate_pct:.2f}%")
    print(f"  Trades:         {metrics.num_trades}")
    print(f"  Profit Factor:  {metrics.profit_factor:.2f}")
    print("=" * 64)
    print(f"  Report: {report_path}")
    print("=" * 64 + "\n")
    return report_path


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit=lim)
