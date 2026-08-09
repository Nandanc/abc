"""Golden Cross / Death Cross backtest runner for Nifty 500."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from src.backtest import apply_backtest_window, backtest_portfolio
from src.config import DATA_DIR, INITIAL_CAPITAL, OUTPUT_DIR, get_backtest_period
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
    download_start, backtest_start, backtest_end = get_backtest_period()
    parser.add_argument(
        "--years",
        type=int,
        default=10,
        help="Backtest window length in years (default: 10 = last 10 years)",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Override backtest start date (YYYY-MM-DD). Ignores --years if set.",
    )
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial portfolio capital (INR)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of stocks (for quick tests)")
    parser.add_argument("--symbols-file", type=Path, default=DATA_DIR / "nifty500_symbols.csv")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--no-risk-management",
        action="store_true",
        help="Use classic death-cross-only exits (no stop loss)",
    )
    parser.add_argument("--stop-loss", type=float, default=None, help="Stop loss %% (e.g. 0.08 = 8%%)")
    parser.add_argument("--trailing-stop", type=float, default=None, help="Trailing stop %% from peak")
    parser.add_argument("--take-profit", type=float, default=None, help="Take profit %% (e.g. 0.40 = 40%%)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.start:
        download_start, backtest_start, backtest_end = get_backtest_period(args.years)
        backtest_start = args.start
        download_start = (
            pd.Timestamp(backtest_start) - pd.Timedelta(days=300)
        ).strftime("%Y-%m-%d")
    else:
        download_start, backtest_start, backtest_end = get_backtest_period(args.years)

    # Apply CLI overrides to risk config
    if args.stop_loss is not None or args.trailing_stop is not None or args.take_profit is not None:
        import src.config as cfg

        if args.stop_loss is not None:
            cfg.STOP_LOSS_PCT = args.stop_loss
        if args.trailing_stop is not None:
            cfg.TRAILING_STOP_PCT = args.trailing_stop
        if args.take_profit is not None:
            cfg.TAKE_PROFIT_PCT = args.take_profit

    logger.info("Loading Nifty 500 symbols...")
    symbols = load_nifty500_symbols(args.symbols_file)
    if args.limit:
        symbols = symbols[: args.limit]
        logger.info("Limited to %d symbols for this run", len(symbols))

    logger.info(
        "Downloading historical data from %s (warmup for %s-day MA)...",
        download_start,
        200,
    )
    price_data = download_stock_data(symbols, start=download_start)

    if not price_data:
        logger.error("No price data downloaded. Check network or symbol list.")
        sys.exit(1)

    logger.info(
        "Running backtest on %d stocks | window: %s to %s | capital: ₹%s",
        len(price_data),
        backtest_start,
        backtest_end,
        f"{args.capital:,.0f}",
    )
    result = backtest_portfolio(
        price_data,
        initial_capital=args.capital,
        use_risk_management=not args.no_risk_management,
    )
    result = apply_backtest_window(result, backtest_start, backtest_end)

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
