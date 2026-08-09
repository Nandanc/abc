"""Configuration for Golden Cross / Death Cross backtest on Nifty 500."""

from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SYMBOLS_FILE = DATA_DIR / "nifty500_symbols.csv"

# Strategy parameters (classic golden / death cross)
SHORT_MA = 50
LONG_MA = 200

# Backtest parameters
INITIAL_CAPITAL = 10_000_000  # INR (10 lakh * 10 = 1 crore for portfolio demo)
BACKTEST_YEARS = 10  # default: last 10 years
MA_WARMUP_DAYS = 300  # extra calendar days before window for 200-day SMA warmup
END_DATE = None  # None = today


def get_backtest_period(years: int = BACKTEST_YEARS) -> tuple[str, str, str]:
    """
    Return (download_start, backtest_start, end_date) as YYYY-MM-DD strings.
    download_start includes warmup history for moving averages.
    """
    end = datetime.now()
    backtest_start = end - timedelta(days=int(years * 365.25))
    download_start = backtest_start - timedelta(days=MA_WARMUP_DAYS)
    return (
        download_start.strftime("%Y-%m-%d"),
        backtest_start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
    )


DOWNLOAD_START_DATE, START_DATE, _ = get_backtest_period()

# Transaction costs (Indian equity typical retail)
BROKERAGE_PCT = 0.0003  # 0.03% per side
STT_PCT = 0.001  # 0.1% on sell (delivery)
SLIPPAGE_PCT = 0.0005  # 0.05% slippage estimate

# Risk-free rate for Sharpe (India 10Y govt bond approx)
RISK_FREE_RATE_ANNUAL = 0.07

# Risk management — entry/exit levels (limits loss per trade)
STOP_LOSS_PCT = 0.08          # Exit if price falls 8% below entry
TRAILING_STOP_PCT = 0.10      # Exit if price falls 10% from highest since entry
USE_TRAILING_STOP = True
TAKE_PROFIT_PCT = 0.40        # Optional target: sell at +40% (None to disable)
REQUIRE_PRICE_ABOVE_MA = True # Entry only if close is above both SMAs on golden cross

# yfinance suffix for NSE stocks
NSE_SUFFIX = ".NS"
