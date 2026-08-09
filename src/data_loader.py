"""Load Nifty 500 symbols and historical OHLCV data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from .config import END_DATE, NSE_SUFFIX, START_DATE, SYMBOLS_FILE

logger = logging.getLogger(__name__)


def load_nifty500_symbols(symbols_file: Path = SYMBOLS_FILE) -> List[str]:
    """Return NSE ticker symbols (without suffix) from the Nifty 500 CSV."""
    df = pd.read_csv(symbols_file)
    symbols = df["Symbol"].astype(str).str.strip().tolist()
    return [s for s in symbols if s and s != "Symbol"]


def to_yfinance_ticker(symbol: str) -> str:
    return f"{symbol}{NSE_SUFFIX}"


def download_stock_data(
    symbols: List[str],
    start: str = START_DATE,
    end: Optional[str] = END_DATE,
    batch_size: int = 50,
) -> Dict[str, pd.DataFrame]:
    """
    Download adjusted close prices for Nifty 500 symbols via yfinance.
    Returns dict mapping symbol -> DataFrame with columns [Open, High, Low, Close, Volume].
    """
    all_data: Dict[str, pd.DataFrame] = {}
    tickers = [to_yfinance_ticker(s) for s in symbols]

    for i in range(0, len(tickers), batch_size):
        batch_tickers = tickers[i : i + batch_size]
        batch_symbols = symbols[i : i + batch_size]
        logger.info("Downloading batch %d-%d of %d symbols...", i + 1, i + len(batch_tickers), len(tickers))

        try:
            raw = yf.download(
                batch_tickers,
                start=start,
                end=end,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as exc:
            logger.warning("Batch download failed: %s", exc)
            continue

        if raw.empty:
            continue

        for j, symbol in enumerate(batch_symbols):
            ticker = batch_tickers[j]
            try:
                if len(batch_tickers) == 1:
                    df = raw.copy()
                else:
                    if ticker not in raw.columns.get_level_values(0):
                        continue
                    df = raw[ticker].copy()

                df = df.dropna(subset=["Close"])
                if len(df) < 250:
                    logger.debug("Skipping %s: insufficient data (%d rows)", symbol, len(df))
                    continue

                df.index = pd.to_datetime(df.index).tz_localize(None)
                all_data[symbol] = df
            except Exception as exc:
                logger.debug("Failed to parse %s: %s", symbol, exc)

    logger.info("Successfully loaded data for %d / %d symbols", len(all_data), len(symbols))
    return all_data


def save_price_cache(data: Dict[str, pd.DataFrame], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    combined = []
    for symbol, df in data.items():
        tmp = df.copy()
        tmp["Symbol"] = symbol
        combined.append(tmp)
    if combined:
        pd.concat(combined).to_parquet(cache_path)


def load_price_cache(cache_path: Path) -> Optional[Dict[str, pd.DataFrame]]:
    if not cache_path.exists():
        return None
    combined = pd.read_parquet(cache_path)
    result: Dict[str, pd.DataFrame] = {}
    for symbol in combined["Symbol"].unique():
        df = combined[combined["Symbol"] == symbol].drop(columns=["Symbol"])
        df.index = pd.to_datetime(df.index)
        result[str(symbol)] = df
    return result
