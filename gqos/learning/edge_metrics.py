from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


def profit_factor(pnl: pd.Series) -> float:
    pnl = pd.to_numeric(pnl, errors="coerce").dropna()
    gross_profit = pnl[pnl > 0].sum()
    gross_loss = abs(pnl[pnl < 0].sum())
    if gross_loss > 0:
        return float(gross_profit / gross_loss)
    if gross_profit > 0:
        return math.inf
    return 0.0


def edge_summary(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "realized_pnl" not in df.columns:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_r": 0.0,
            "total_pnl": 0.0,
        }

    pnl = pd.to_numeric(df["realized_pnl"], errors="coerce").fillna(0.0)
    wins = int((pnl > 0).sum())
    losses = int((pnl < 0).sum())
    total = int(len(df))
    avg_r = 0.0
    if "actual_r" in df.columns:
        avg_r = pd.to_numeric(df["actual_r"], errors="coerce").dropna().mean()
        if pd.isna(avg_r):
            avg_r = 0.0

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / total * 100.0) if total else 0.0, 2),
        "profit_factor": round(profit_factor(pnl), 4),
        "expectancy": round(float(pnl.mean()) if total else 0.0, 4),
        "avg_r": round(float(avg_r), 4),
        "total_pnl": round(float(pnl.sum()), 4),
    }


def rolling_edge(df: pd.DataFrame, windows: Iterable[int] = (20, 50, 100)) -> pd.DataFrame:
    rows = []
    if df is None or df.empty:
        return pd.DataFrame(rows)

    ordered = _sort_outcomes(df)
    for window in windows:
        subset = ordered.tail(int(window))
        summary = edge_summary(subset)
        summary["window"] = int(window)
        rows.append(summary)
    return pd.DataFrame(rows)


def grouped_edge(
    df: pd.DataFrame,
    group_col: str,
    window: int = 50,
    min_trades: int = 3,
) -> pd.DataFrame:
    if df is None or df.empty or group_col not in df.columns:
        return pd.DataFrame()

    ordered = _sort_outcomes(df)
    rows = []
    for key, group in ordered.groupby(group_col, dropna=True):
        subset = group.tail(int(window))
        if len(subset) < min_trades:
            continue
        summary = edge_summary(subset)
        summary[group_col] = key
        summary["window"] = int(window)
        rows.append(summary)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["profit_factor", "expectancy"], ascending=False)


def _sort_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    if "close_time" in df.columns:
        ordered = df.copy()
        ordered["close_time"] = pd.to_datetime(ordered["close_time"], errors="coerce")
        return ordered.sort_values("close_time")
    return df.copy()
