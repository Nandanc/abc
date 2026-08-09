# systematic_trading

Systematic trading backtests for Indian equities — starting with **Golden Cross / Death Cross** on **Nifty 500**.

Repository: https://github.com/Nandanc/systematic_trading

## Strategy (Manual Rules)

| Signal | Condition | Action |
|--------|-----------|--------|
| **Golden Cross** | 50-day SMA crosses **above** 200-day SMA | **BUY** (enter long) |
| **Death Cross** | 50-day SMA crosses **below** 200-day SMA | **SELL** (exit long) |

Hold the position between a golden cross and the next death cross. No short selling.

See [docs/STRATEGY.md](docs/STRATEGY.md) for a full manual walkthrough.

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

### Options

```bash
python main.py                    # last 10 years (default)
python main.py --years 10         # explicit 10-year window
python main.py --years 5          # last 5 years
python main.py --start 2016-01-01 # custom start (with MA warmup auto-fetched)
python main.py --limit 20         # quick test on 20 stocks
```

## Outputs

Reports and charts are saved to `outputs/`:

- `backtest_report_*.md` — Full summary report
- `equity_curve_*.png` — Portfolio equity curve + drawdown chart
- `stock_summary_*.csv` — Per-stock metrics
- `all_trades_*.csv` — All round-trip trades

## Metrics Calculated

- Total Return, CAGR
- Max Drawdown & duration
- Sharpe, Sortino, Calmar ratios
- Win rate, profit factor, expectancy
- Average win/loss, best/worst trade
- Volatility, exposure, recovery factor, ulcer index

## Disclaimer

This is for educational backtesting only. Past performance does not guarantee future results. Not financial advice.
