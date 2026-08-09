"""Configuration for Golden Cross / Death Cross backtest on Nifty 500."""

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
START_DATE = "2015-01-01"
END_DATE = None  # None = today

# Transaction costs (Indian equity typical retail)
BROKERAGE_PCT = 0.0003  # 0.03% per side
STT_PCT = 0.001  # 0.1% on sell (delivery)
SLIPPAGE_PCT = 0.0005  # 0.05% slippage estimate

# Risk-free rate for Sharpe (India 10Y govt bond approx)
RISK_FREE_RATE_ANNUAL = 0.07

# yfinance suffix for NSE stocks
NSE_SUFFIX = ".NS"
