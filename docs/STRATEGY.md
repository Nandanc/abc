# Golden Cross & Death Cross Strategy — Manual Guide

## What You Are Trading

This is a **trend-following** strategy based on two moving averages:

- **Short MA (50-day):** Average closing price over the last 50 trading days (~2.5 months)
- **Long MA (200-day):** Average closing price over the last 200 trading days (~10 months)

## The Two Signals

### 1. Golden Cross (BUY)

**When:** The 50-day SMA crosses **from below to above** the 200-day SMA.

**What it means:** Short-term momentum has turned stronger than long-term momentum. Traders interpret this as a potential **bullish trend** starting.

**Manual action:** Buy the stock at market close on the day of the cross (or next day open).

**Example:**

```
Day 198:  SMA50 = ₹980,  SMA200 = ₹1000  (50 below 200)
Day 199:  SMA50 = ₹1005, SMA200 = ₹1000  (50 crossed above 200) → GOLDEN CROSS → BUY
```

### 2. Death Cross (SELL)

**When:** The 50-day SMA crosses **from above to below** the 200-day SMA.

**What it means:** Short-term momentum has weakened below long-term momentum. Traders interpret this as a potential **bearish trend** starting.

**Manual action:** Sell your entire position at market close on the day of the cross (or next day open).

**Example:**

```
Day 350:  SMA50 = ₹1050, SMA200 = ₹1040  (50 above 200)
Day 351:  SMA50 = ₹1035, SMA200 = ₹1040  (50 crossed below 200) → DEATH CROSS → SELL
```

## Step-by-Step Manual Trading Workflow

### Daily routine (end of day)

1. **Update data** — Get today's closing price for each Nifty 500 stock.
2. **Calculate SMAs** — Compute 50-day and 200-day simple moving averages.
3. **Check crosses** — Compare today's SMAs vs yesterday's SMAs:
   - If SMA50 was ≤ SMA200 yesterday AND SMA50 > SMA200 today → **Golden Cross → BUY**
   - If SMA50 was ≥ SMA200 yesterday AND SMA50 < SMA200 today → **Death Cross → SELL**
4. **Execute orders** — Place buy/sell orders for signaled stocks.
5. **Log trades** — Record entry date, price, exit date, price, and P&L.

### Position rules

| Rule | Description |
|------|-------------|
| One direction only | Long only — no short selling |
| Full position | Buy with allocated capital; sell entire position on exit |
| No re-entry mid-trend | Only enter on golden cross, not just because price is above MA |
| Patience | Need 200 trading days of history before first valid signal |

## Nifty 500 Universe

We use all **Nifty 500** constituents — the top 500 Indian companies by full market capitalization on NSE. Each stock is backtested with **equal capital allocation** (portfolio capital ÷ number of stocks).

## Transaction Costs (Backtest Assumptions)

| Cost | Rate | Applied |
|------|------|---------|
| Brokerage | 0.03% | Buy & Sell |
| STT | 0.10% | Sell only (delivery) |
| Slippage | 0.05% | Buy & Sell |

## Key Metrics to Watch

After backtesting, evaluate the strategy using:

| Metric | What it tells you |
|--------|-------------------|
| **Total Return / CAGR** | How much the strategy grew over time |
| **Max Drawdown** | Largest peak-to-trough decline — your worst pain period |
| **Sharpe Ratio** | Return per unit of risk (>1 is decent, >2 is strong) |
| **Win Rate** | % of trades that were profitable |
| **Profit Factor** | Gross profits ÷ gross losses (>1.5 is good) |
| **Expectancy** | Average expected return per trade |
| **Calmar Ratio** | CAGR ÷ Max Drawdown — reward per unit of drawdown pain |
| **Ulcer Index** | Depth and duration of drawdowns combined |

## Important Caveats

1. **Lag:** Moving averages react slowly; you enter after a move has already started.
2. **Whipsaws:** In sideways markets, you may get false signals and small losses.
3. **Long-only:** You earn nothing (or lose) in prolonged bear markets while flat.
4. **Survivorship:** Index constituents change; historical backtests may not reflect today's list perfectly.
5. **Not advice:** Educational backtest only.

## Automation

The Python backtest in this repo automates every step above:

```
Download Nifty 500 prices → Calculate SMAs → Detect crosses → Simulate trades → Report metrics
```

Run: `python main.py`
