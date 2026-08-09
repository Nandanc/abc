"""Golden Cross / Death Cross signal generation."""

from __future__ import annotations

import pandas as pd

from .config import LONG_MA, SHORT_MA


def add_moving_averages(df: pd.DataFrame, short: int = SHORT_MA, long: int = LONG_MA) -> pd.DataFrame:
    out = df.copy()
    out["SMA_short"] = out["Close"].rolling(window=short, min_periods=short).mean()
    out["SMA_long"] = out["Close"].rolling(window=long, min_periods=long).mean()
    return out


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate golden cross (buy) and death cross (sell) signals.

    Golden Cross: 50-day SMA crosses above 200-day SMA -> BUY
    Death Cross:  50-day SMA crosses below 200-day SMA -> SELL

    Position is 1 (long) between a golden cross and the next death cross.
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


def extract_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Extract round-trip trades from signal DataFrame."""
    trades = []
    entry_date = None
    entry_price = None

    for date, row in df.iterrows():
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
