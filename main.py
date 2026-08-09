"""Golden Cross / Death Cross backtest runner for Nifty 500."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.backtest import backtest_portfolio
from src.config import DATA_DIR, INITIAL_CAPITAL, OUTPUT_DIR, START_DATE
from src.data_loader import download_stock_data, load_nifty500_symbols
from src.report import generate_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest Golden Cross / Death Cross strategy on Nifty 500 stocks",
    )
    parser.add_argument("--start", default=START_DATE, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial portfolio capital (INR)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of stocks (for quick tests)")
    parser.add_argument("--symbols-file", type=Path, default=DATA_DIR / "nifty500_symbols.csv")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("Loading Nifty 500 symbols...")
    symbols = load_nifty500_symbols(args.symbols_file)
    if args.limit:
        symbols = symbols[: args.limit]
        logger.info("Limited to %d symbols for this run", len(symbols))

    logger.info("Downloading historical data from %s...", args.start)
    price_data = download_stock_data(symbols, start=args.start)

    if not price_data:
        logger.error("No price data downloaded. Check network or symbol list.")
        sys.exit(1)

    logger.info("Running backtest on %d stocks with ₹%s capital...", len(price_data), f"{args.capital:,.0f}")
    result = backtest_portfolio(price_data, initial_capital=args.capital)

    logger.info("Generating report and charts...")
    report_path = generate_report(result, output_dir=args.output_dir)

    m = result.metrics
    print("\n" + "=" * 60)
    print("  GOLDEN CROSS / DEATH CROSS — NIFTY 500 BACKTEST SUMMARY")
    print("=" * 60)
    print(f"  Stocks tested:        {len(result.stock_results)}")
    print(f"  Total Return:         {m.total_return_pct:.2f}%")
    print(f"  CAGR:                 {m.cagr_pct:.2f}%")
    print(f"  Max Drawdown:         {m.max_drawdown_pct:.2f}%")
    print(f"  Sharpe Ratio:         {m.sharpe_ratio:.2f}")
    print(f"  Win Rate:             {m.win_rate_pct:.2f}%")
    print(f"  Total Trades:         {m.num_trades}")
    print(f"  Profit Factor:        {m.profit_factor:.2f}")
    print("=" * 60)
    print(f"  Full report: {report_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
