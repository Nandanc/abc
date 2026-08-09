# Golden Cross / Death Cross Backtest

Systematic trading backtest for the **Golden Cross** and **Death Cross** strategy on **Nifty 500** stocks.

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
python main.py --start 2015-01-01 --capital 10000000
python main.py --limit 20   # quick test on 20 stocks
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
