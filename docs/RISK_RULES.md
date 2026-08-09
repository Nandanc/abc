## Risk-Managed Entry & Exit (Loss Control)

Use these rules to **cap how much you lose** on each trade.

### ENTRY — when to buy

| Rule | Condition |
|------|-----------|
| **Signal** | 50-day SMA crosses **above** 200-day SMA (golden cross) |
| **Confirmation** | Close price is **above both** SMAs |
| **Entry price** | Close on signal day (or next day open) |

**Example:** Stock at ₹1,000 → you **BUY** at ₹1,000

| Level | Price | Meaning |
|-------|-------|---------|
| **Entry** | ₹1,000 | Your buy price |
| **Stop loss** | ₹920 (−8%) | Max loss if wrong |
| **Take profit** | ₹1,400 (+40%) | Target if right |

### EXIT — when to sell (first trigger wins)

| Priority | Rule | Action |
|----------|------|--------|
| 1 | **Stop loss** | Price falls **8%** below entry → **SELL** (cut loss) |
| 2 | **Trailing stop** | Price falls **10%** from highest since entry → **SELL** (protect profit) |
| 3 | **Take profit** | Price rises **40%** above entry → **SELL** (lock gain) |
| 4 | **Death cross** | 50 SMA crosses below 200 SMA → **SELL** (trend ended) |

### Why this helps

- **Without stops:** average loss was **−14%**, worst trade **−82%**
- **With 8% stop:** worst loss capped near **−8%**, average loss **~−5 to −6%**

### Tuning (in `src/config.py` or CLI)

```bash
python main.py --stop-loss 0.06    # tighter: 6% max loss
python main.py --stop-loss 0.10    # wider: 10% max loss
python main.py --take-profit 0.50  # 50% target
python main.py --no-risk-management  # old style: death cross only
```

**Trade-off:** Tighter stops = smaller losses but may exit good trades early and reduce total return.
