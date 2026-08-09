"""Generate summary reports and equity curve charts."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import seaborn as sns
from tabulate import tabulate

from .backtest import PortfolioBacktestResult, summarize_stock_metrics
from .config import INITIAL_CAPITAL, OUTPUT_DIR, SHORT_MA, LONG_MA
from .metrics import MetricsResult

logger = logging.getLogger(__name__)

sns.set_theme(style="whitegrid")


def _metrics_to_dict(m: MetricsResult) -> dict:
    return {
        "Total Return (%)": f"{m.total_return_pct:.2f}",
        "CAGR (%)": f"{m.cagr_pct:.2f}",
        "Max Drawdown (%)": f"{m.max_drawdown_pct:.2f}",
        "Max DD Duration (days)": m.max_drawdown_duration_days,
        "Sharpe Ratio": f"{m.sharpe_ratio:.2f}",
        "Sortino Ratio": f"{m.sortino_ratio:.2f}",
        "Calmar Ratio": f"{m.calmar_ratio:.2f}",
        "Annual Volatility (%)": f"{m.volatility_annual_pct:.2f}",
        "Win Rate (%)": f"{m.win_rate_pct:.2f}",
        "Number of Trades": m.num_trades,
        "Avg Trade Return (%)": f"{m.avg_trade_return_pct:.2f}",
        "Avg Win (%)": f"{m.avg_win_pct:.2f}",
        "Avg Loss (%)": f"{m.avg_loss_pct:.2f}",
        "Profit Factor": f"{m.profit_factor:.2f}",
        "Expectancy (%)": f"{m.expectancy_pct:.2f}",
        "Best Trade (%)": f"{m.best_trade_pct:.2f}",
        "Worst Trade (%)": f"{m.worst_trade_pct:.2f}",
        "Avg Holding (days)": f"{m.avg_holding_days:.1f}",
        "Exposure (%)": f"{m.exposure_pct:.2f}",
        "Recovery Factor": f"{m.recovery_factor:.2f}",
        "Ulcer Index": f"{m.ulcer_index:.2f}",
    }


def plot_equity_curve(
    equity: pd.Series,
    output_path: Path,
    title: str = "Portfolio Equity Curve",
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1 = axes[0]
    ax1.plot(equity.index, equity.values, color="#2E86AB", linewidth=1.5, label="Equity")
    ax1.fill_between(equity.index, equity.values, equity.iloc[0], alpha=0.1, color="#2E86AB")
    ax1.set_title(title, fontsize=14, fontweight="bold")
    ax1.set_ylabel("Portfolio Value (INR)")
    ax1.legend(loc="upper left")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.YearLocator())

    # Drawdown subplot
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max * 100
    ax2 = axes[1]
    ax2.fill_between(drawdown.index, drawdown.values, 0, color="#E74C3C", alpha=0.6)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Equity curve saved to %s", output_path)


def plot_drawdown_distribution(stock_summary: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(stock_summary["Max Drawdown %"], bins=30, kde=True, ax=ax, color="#E74C3C")
    ax.set_title("Distribution of Max Drawdown Across Nifty 500 Stocks")
    ax.set_xlabel("Max Drawdown (%)")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_return_distribution(stock_summary: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(stock_summary["Total Return %"], bins=30, kde=True, ax=ax, color="#2E86AB")
    ax.set_title("Distribution of Total Returns Across Nifty 500 Stocks")
    ax.set_xlabel("Total Return (%)")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_report(result: PortfolioBacktestResult, output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"backtest_report_{timestamp}.md"

    stock_summary = summarize_stock_metrics(result.stock_results)
    portfolio_metrics = _metrics_to_dict(result.metrics)

    # Charts
    equity_chart = output_dir / f"equity_curve_{timestamp}.png"
    dd_chart = output_dir / f"drawdown_distribution_{timestamp}.png"
    ret_chart = output_dir / f"return_distribution_{timestamp}.png"

    plot_equity_curve(
        result.equity_curve,
        equity_chart,
        title=f"Nifty 500 Golden Cross ({SHORT_MA}/{LONG_MA}) Portfolio Equity Curve",
    )
    plot_drawdown_distribution(stock_summary, dd_chart)
    plot_return_distribution(stock_summary, ret_chart)

    stock_csv = output_dir / f"stock_summary_{timestamp}.csv"
    stock_summary.to_csv(stock_csv, index=False)
    if not result.aggregate_trades.empty:
        result.aggregate_trades.to_csv(output_dir / f"all_trades_{timestamp}.csv", index=False)

    # Markdown report
    lines = [
        "# Golden Cross / Death Cross Backtest Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Strategy",
        "",
        f"- **Golden Cross (BUY):** {SHORT_MA}-day SMA crosses **above** {LONG_MA}-day SMA",
        f"- **Death Cross (SELL):** {SHORT_MA}-day SMA crosses **below** {LONG_MA}-day SMA",
        f"- **Universe:** Nifty 500 ({len(result.stock_results)} stocks with sufficient data)",
        f"- **Initial Capital:** ₹{INITIAL_CAPITAL:,.0f}",
        f"- **Allocation:** Equal weight per stock (₹{INITIAL_CAPITAL / len(result.stock_results):,.0f} each)",
        "",
        "## Portfolio Performance Summary",
        "",
        tabulate(
            [[k, v] for k, v in portfolio_metrics.items()],
            headers=["Metric", "Value"],
            tablefmt="pipe",
        ),
        "",
        "## Cross-Stock Statistics",
        "",
        f"- **Stocks with positive return:** {len(stock_summary[stock_summary['Total Return %'] > 0])} / {len(stock_summary)}",
        f"- **Median Total Return:** {stock_summary['Total Return %'].median():.2f}%",
        f"- **Median Max Drawdown:** {stock_summary['Max Drawdown %'].median():.2f}%",
        f"- **Median Win Rate:** {stock_summary['Win Rate %'].median():.2f}%",
        f"- **Median Sharpe:** {stock_summary['Sharpe'].median():.2f}",
        "",
        "## Top 10 Performers",
        "",
        tabulate(stock_summary.head(10).values, headers=stock_summary.columns, tablefmt="pipe", floatfmt=".2f"),
        "",
        "## Bottom 10 Performers",
        "",
        tabulate(stock_summary.tail(10).values, headers=stock_summary.columns, tablefmt="pipe", floatfmt=".2f"),
        "",
        "## Charts",
        "",
        f"![Equity Curve]({equity_chart.name})",
        "",
        f"![Drawdown Distribution]({dd_chart.name})",
        "",
        f"![Return Distribution]({ret_chart.name})",
        "",
        "## Files Generated",
        "",
        f"- `{equity_chart.name}` — Portfolio equity curve + drawdown",
        f"- `{stock_csv.name}` — Per-stock metrics CSV",
        f"- `{dd_chart.name}` — Drawdown distribution",
        f"- `{ret_chart.name}` — Return distribution",
    ]

    report_path.write_text("\n".join(lines))
    logger.info("Report saved to %s", report_path)
    return report_path
