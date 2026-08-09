"""Performance metrics for backtest results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .config import RISK_FREE_RATE_ANNUAL


@dataclass
class MetricsResult:
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    max_drawdown_duration_days: int
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility_annual_pct: float
    win_rate_pct: float
    num_trades: int
    avg_trade_return_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    avg_holding_days: float
    exposure_pct: float
    recovery_factor: float
    ulcer_index: float


def _annualize_factor(daily_returns: pd.Series) -> float:
    return 252


def compute_max_drawdown(equity: pd.Series) -> tuple[float, int]:
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_dd = drawdown.min()
    if max_dd >= 0:
        return 0.0, 0

    # Duration: longest stretch below previous peak
    in_drawdown = drawdown < 0
    max_duration = 0
    current_duration = 0
    for val in in_drawdown:
        if val:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return abs(max_dd) * 100, max_duration


def compute_ulcer_index(equity: pd.Series) -> float:
    rolling_max = equity.cummax()
    drawdown_pct = ((equity - rolling_max) / rolling_max) * 100
    return float(np.sqrt(np.mean(drawdown_pct ** 2)))


def compute_metrics(
    equity_curve: pd.Series,
    daily_returns: pd.Series,
    trades: Optional[pd.DataFrame] = None,
    exposure_series: Optional[pd.Series] = None,
) -> MetricsResult:
    equity = equity_curve.dropna()
    if len(equity) < 2:
        return MetricsResult(
            total_return_pct=0, cagr_pct=0, max_drawdown_pct=0,
            max_drawdown_duration_days=0, sharpe_ratio=0, sortino_ratio=0,
            calmar_ratio=0, volatility_annual_pct=0, win_rate_pct=0,
            num_trades=0, avg_trade_return_pct=0, avg_win_pct=0,
            avg_loss_pct=0, profit_factor=0, expectancy_pct=0,
            best_trade_pct=0, worst_trade_pct=0, avg_holding_days=0,
            exposure_pct=0, recovery_factor=0, ulcer_index=0,
        )

    initial = equity.iloc[0]
    final = equity.iloc[-1]
    total_return_pct = ((final / initial) - 1) * 100

    days = (equity.index[-1] - equity.index[0]).days
    years = max(days / 365.25, 1 / 365.25)
    cagr_pct = ((final / initial) ** (1 / years) - 1) * 100

    max_dd_pct, max_dd_duration = compute_max_drawdown(equity)
    ulcer = compute_ulcer_index(equity)

    ann_factor = _annualize_factor(daily_returns)
    excess_daily = daily_returns - (RISK_FREE_RATE_ANNUAL / ann_factor)
    vol_annual = daily_returns.std() * np.sqrt(ann_factor)
    sharpe = (excess_daily.mean() / daily_returns.std() * np.sqrt(ann_factor)) if daily_returns.std() > 0 else 0

    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std() * np.sqrt(ann_factor) if len(downside) > 0 else 0
    sortino = ((daily_returns.mean() * ann_factor - RISK_FREE_RATE_ANNUAL) / downside_std) if downside_std > 0 else 0

    calmar = (cagr_pct / max_dd_pct) if max_dd_pct > 0 else 0
    recovery = (total_return_pct / max_dd_pct) if max_dd_pct > 0 else 0

    # Trade-level metrics
    ret_col = "return_pct_net" if trades is not None and "return_pct_net" in trades.columns else "return_pct"
    if trades is not None and not trades.empty and ret_col in trades.columns:
        trade_returns = trades[ret_col]
        wins = trade_returns[trade_returns > 0]
        losses = trade_returns[trade_returns <= 0]
        num_trades = len(trade_returns)
        win_rate = (len(wins) / num_trades) * 100 if num_trades else 0
        avg_trade = trade_returns.mean() * 100
        avg_win = wins.mean() * 100 if len(wins) else 0
        avg_loss = losses.mean() * 100 if len(losses) else 0
        gross_profit = wins.sum()
        gross_loss = abs(losses.sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        expectancy = trade_returns.mean() * 100
        best_trade = trade_returns.max() * 100
        worst_trade = trade_returns.min() * 100
        avg_holding = trades["holding_days"].mean() if "holding_days" in trades.columns else 0
    else:
        num_trades = 0
        win_rate = 0
        avg_trade = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0
        expectancy = 0
        best_trade = 0
        worst_trade = 0
        avg_holding = 0

    exposure_pct = exposure_series.mean() * 100 if exposure_series is not None else 0

    return MetricsResult(
        total_return_pct=total_return_pct,
        cagr_pct=cagr_pct,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration_days=max_dd_duration,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        volatility_annual_pct=vol_annual * 100,
        win_rate_pct=win_rate,
        num_trades=num_trades,
        avg_trade_return_pct=avg_trade,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        profit_factor=profit_factor if profit_factor != float("inf") else 999.99,
        expectancy_pct=expectancy,
        best_trade_pct=best_trade,
        worst_trade_pct=worst_trade,
        avg_holding_days=avg_holding,
        exposure_pct=exposure_pct,
        recovery_factor=recovery,
        ulcer_index=ulcer,
    )
