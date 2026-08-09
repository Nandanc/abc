"""Golden Cross / Death Cross with risk-managed entry and exit levels."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .config import (
    LONG_MA,
    REQUIRE_PRICE_ABOVE_MA,
    SHORT_MA,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TRAILING_STOP_PCT,
    USE_TRAILING_STOP,
)


def add_moving_averages(df: pd.DataFrame, short: int = SHORT_MA, long: int = LONG_MA) -> pd.DataFrame:
    out = df.copy()
    out["SMA_short"] = out["Close"].rolling(window=short, min_periods=short).mean()
    out["SMA_long"] = out["Close"].rolling(window=long, min_periods=long).mean()
    return out


def _golden_cross_row(row: pd.Series, prev_row: pd.Series) -> bool:
    return bool(
        row["SMA_short"] > row["SMA_long"]
        and prev_row["SMA_short"] <= prev_row["SMA_long"]
    )


def _death_cross_row(row: pd.Series, prev_row: pd.Series) -> bool:
    return bool(
        row["SMA_short"] < row["SMA_long"]
        and prev_row["SMA_short"] >= prev_row["SMA_long"]
    )


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classic golden/death cross signals (no stop loss).
    Kept for reference; backtest uses risk-managed signals by default.
    """
    out = add_moving_averages(df)
    out["golden_cross"] = (
        (out["SMA_short"] > out["SMA_long"])
        & (out["SMA_short"].shift(1) <= out["SMA_long"].shift(1))
    )
    out["death_cross"] = (
        (out["SMA_short"] < out["SMA_long"])
        & (out["SMA_short"].shift(1) >= out["SMA_long"].shift(1))
    )

    position = 0
    positions = []
    for golden, death in zip(out["golden_cross"], out["death_cross"]):
        if golden:
            position = 1
        elif death:
            position = 0
        positions.append(position)

    out["position"] = positions
    out["position"] = out["position"].astype(int)
    return out


def generate_risk_managed_signals(
    df: pd.DataFrame,
    stop_loss_pct: float = STOP_LOSS_PCT,
    trailing_stop_pct: float = TRAILING_STOP_PCT,
    take_profit_pct: Optional[float] = TAKE_PROFIT_PCT,
    use_trailing_stop: bool = USE_TRAILING_STOP,
    require_price_above_ma: bool = REQUIRE_PRICE_ABOVE_MA,
) -> pd.DataFrame:
    """
    Simulate trades with explicit entry/exit levels to cap losses.

    ENTRY (buy):
      - Golden cross: 50-day SMA crosses above 200-day SMA
      - Optional filter: close must be above both SMAs

    EXIT (sell) — first trigger wins:
      1. Stop loss: price falls X% below entry
      2. Trailing stop: price falls X% from highest high since entry
      3. Take profit: price rises to target % above entry
      4. Death cross: 50-day SMA crosses below 200-day SMA
    """
    out = add_moving_averages(df)
    out["position"] = 0
    out["stop_loss_price"] = float("nan")
    out["take_profit_price"] = float("nan")
    out["entry_signal"] = False
    out["exit_signal"] = False
    out["exit_reason"] = ""
    out["trade_exit_price"] = float("nan")

    in_position = False
    entry_price = 0.0
    highest_since_entry = 0.0

    prev_row = None
    for date, row in out.iterrows():
        if prev_row is None:
            prev_row = row
            continue

        golden = _golden_cross_row(row, prev_row)
        death = _death_cross_row(row, prev_row)
        close = float(row["Close"])
        low = float(row["Low"])
        high = float(row["High"])

        if not in_position:
            entry_ok = golden
            if require_price_above_ma and golden:
                entry_ok = close > float(row["SMA_short"]) and close > float(row["SMA_long"])

            if entry_ok:
                in_position = True
                entry_price = close
                highest_since_entry = high
                out.at[date, "position"] = 1
                out.at[date, "entry_signal"] = True
                out.at[date, "stop_loss_price"] = entry_price * (1 - stop_loss_pct)
                if take_profit_pct is not None:
                    out.at[date, "take_profit_price"] = entry_price * (1 + take_profit_pct)
        else:
            highest_since_entry = max(highest_since_entry, high)
            hard_stop = entry_price * (1 - stop_loss_pct)
            trail_stop = highest_since_entry * (1 - trailing_stop_pct)
            effective_stop = max(hard_stop, trail_stop) if use_trailing_stop else hard_stop

            exit_reason = None
            exit_price = close

            if low <= effective_stop:
                exit_price = effective_stop
                exit_reason = "trailing_stop" if effective_stop > hard_stop else "stop_loss"
            elif take_profit_pct is not None and high >= entry_price * (1 + take_profit_pct):
                exit_price = entry_price * (1 + take_profit_pct)
                exit_reason = "take_profit"
            elif death:
                exit_reason = "death_cross"

            if exit_reason:
                in_position = False
                out.at[date, "position"] = 0
                out.at[date, "exit_signal"] = True
                out.at[date, "exit_reason"] = exit_reason
                out.at[date, "trade_exit_price"] = exit_price
                entry_price = 0.0
                highest_since_entry = 0.0
            else:
                out.at[date, "position"] = 1
                out.at[date, "stop_loss_price"] = effective_stop
                if take_profit_pct is not None:
                    out.at[date, "take_profit_price"] = entry_price * (1 + take_profit_pct)

        prev_row = row

    return out


def extract_trades_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    """Extract round-trip trades from risk-managed signal DataFrame."""
    trades = []
    entry_date = None
    entry_price = None
    stop_at_entry = None
    target_at_entry = None

    prev_row = None
    for date, row in signals.iterrows():
        if row.get("entry_signal", False):
            entry_date = date
            entry_price = float(row["Close"])
            stop_at_entry = float(row["stop_loss_price"])
            target_at_entry = (
                float(row["take_profit_price"])
                if pd.notna(row.get("take_profit_price"))
                else None
            )
        elif row.get("exit_signal", False) and entry_date is not None:
            exit_price = (
                float(row["trade_exit_price"])
                if pd.notna(row.get("trade_exit_price"))
                else float(row["Close"])
            )
            pnl_pct = (exit_price - entry_price) / entry_price
            exit_reason = str(row.get("exit_reason", "unknown"))
            trades.append(
                {
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "stop_loss": stop_at_entry,
                    "take_profit": target_at_entry,
                    "return_pct": pnl_pct,
                    "exit_reason": exit_reason,
                    "holding_days": (date - entry_date).days,
                }
            )
            entry_date = None
            entry_price = None
            stop_at_entry = None
            target_at_entry = None

        prev_row = row

    return pd.DataFrame(trades)


def extract_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Extract trades from classic golden/death signals (legacy)."""
    signals = generate_signals(df)
    trades = []
    entry_date = None
    entry_price = None

    for date, row in signals.iterrows():
        if row["golden_cross"] and entry_date is None:
            entry_date = date
            entry_price = row["Close"]
        elif row["death_cross"] and entry_date is not None:
            exit_price = row["Close"]
            pnl_pct = (exit_price - entry_price) / entry_price
            trades.append(
                {
                    "entry_date": entry_date,
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": pnl_pct,
                    "holding_days": (date - entry_date).days,
                }
            )
            entry_date = None
            entry_price = None

    return pd.DataFrame(trades)
