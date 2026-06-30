import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

logger = logging.getLogger("GQOS.SimulationAnalyzer")

VIRTUAL_OUTCOMES_PATH = Path(os.getenv("GQOS_VIRTUAL_OUTCOMES_PATH", "data/learning/virtual_trade_outcomes.jsonl"))
MISSED_OUTCOMES_PATH = Path(os.getenv("GQOS_MISSED_OUTCOMES_PATH", "data/learning/missed_opportunity_outcomes.jsonl"))
RECOMMENDATIONS_PATH = Path(os.getenv("GQOS_SIM_RECOMMENDATIONS_PATH", "data/learning/simulation_recommendations.json"))

MIN_SAMPLES = int(os.getenv("GQOS_SIM_RECOMMEND_MIN_SAMPLES", "20"))
MAX_PF_ADJUST = float(os.getenv("GQOS_SIM_MAX_PF_ADJUST", "0.05"))
MAX_EXPR_ADJUST = float(os.getenv("GQOS_SIM_MAX_EXPR_ADJUST", "0.02"))


def _read_jsonl(path: Path, limit: int = 50000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
                if len(rows) > limit:
                    rows.pop(0)
            except json.JSONDecodeError:
                continue
    return rows


def _clean_symbol(symbol: str) -> str:
    value = str(symbol or "").upper()
    for suffix in (".M", "M"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    if value == "USTEC":
        return "NAS100"
    if value == "DE30":
        return "GER40"
    return value


def _direction(side: str) -> str:
    value = str(side or "").upper()
    if "BUY" in value or "LONG" in value:
        return "LONG"
    if "SELL" in value or "SHORT" in value:
        return "SHORT"
    return value


def _is_win(outcome: str) -> bool:
    value = str(outcome or "")
    return value.startswith("WIN") or value.startswith("TIMEOUT_WIN")


def _bounded(value: float, max_abs: float) -> float:
    return max(-max_abs, min(max_abs, value))


def build_simulation_recommendations() -> dict[str, Any]:
    virtual = _read_jsonl(VIRTUAL_OUTCOMES_PATH)
    missed = _read_jsonl(MISSED_OUTCOMES_PATH)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    context_grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in virtual:
        symbol = _clean_symbol(row.get("clean_symbol") or row.get("symbol"))
        side = _direction(row.get("side"))
        if symbol and side in {"LONG", "SHORT"}:
            enriched = {**row, "_source": "continuous"}
            grouped[(symbol, side)].append(enriched)
            context_grouped[(
                symbol,
                side,
                str(row.get("session") or "UNKNOWN"),
                str(row.get("market_session") or "UNKNOWN"),
                str(row.get("spread_bucket") or "UNKNOWN"),
                str(row.get("volatility_bucket") or "UNKNOWN"),
            )].append(enriched)

    for row in missed:
        symbol = _clean_symbol(row.get("source_symbol") or row.get("symbol"))
        side = _direction(row.get("side"))
        if symbol and side in {"LONG", "SHORT"}:
            grouped[(symbol, side)].append({**row, "_source": "missed"})

    recommendations = {}
    for (symbol, side), rows in grouped.items():
        rec = _make_recommendation(symbol, side, rows)
        if rec:
            recommendations[f"{symbol}:{side}"] = rec

    context_recommendations = {}
    context_min_samples = max(10, MIN_SAMPLES // 2)
    for (symbol, side, session, market_session, spread_bucket, vol_bucket), rows in context_grouped.items():
        rec = _make_recommendation(symbol, side, rows, min_samples=context_min_samples)
        if rec:
            rec.update({
                "session": session,
                "market_session": market_session,
                "spread_bucket": spread_bucket,
                "volatility_bucket": vol_bucket,
            })
            context_recommendations[f"{symbol}:{side}:{session}:{market_session}:{spread_bucket}:{vol_bucket}"] = rec

    payload = {
        "min_samples": MIN_SAMPLES,
        "context_min_samples": context_min_samples,
        "virtual_rows": len(virtual),
        "missed_rows": len(missed),
        "recommendations": recommendations,
        "context_recommendations": context_recommendations,
    }
    RECOMMENDATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECOMMENDATIONS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("[SimulationAnalyzer] wrote %s recommendations", len(recommendations))
    return payload


def _make_recommendation(symbol: str, side: str, rows: list[dict[str, Any]], min_samples: int | None = None) -> dict[str, Any] | None:
    required_samples = min_samples or MIN_SAMPLES
    if len(rows) < required_samples:
        return None
    actual_rs = [float(r.get("actual_r") or 0.0) for r in rows]
    avg_r = mean(actual_rs)
    win_rate = sum(1 for r in rows if _is_win(str(r.get("outcome")))) / len(rows)
    missed_count = sum(1 for r in rows if r.get("_source") == "missed")

    if avg_r >= 0.15 and win_rate >= 0.52:
        pf_adjust = -min(MAX_PF_ADJUST, 0.02 + avg_r * 0.03)
        expr_adjust = -min(MAX_EXPR_ADJUST, avg_r * 0.01)
        action = "RELAX_SLIGHTLY"
    elif avg_r <= -0.15 or win_rate <= 0.45:
        pf_adjust = min(MAX_PF_ADJUST, 0.02 + abs(avg_r) * 0.03)
        expr_adjust = min(MAX_EXPR_ADJUST, abs(avg_r) * 0.01)
        action = "TIGHTEN_SLIGHTLY"
    else:
        pf_adjust = 0.0
        expr_adjust = 0.0
        action = "NEUTRAL"

    return {
        "symbol": symbol,
        "side": side,
        "samples": len(rows),
        "missed_samples": missed_count,
        "win_rate": round(win_rate, 4),
        "avg_r": round(avg_r, 4),
        "pf_threshold_adjust": round(_bounded(pf_adjust, MAX_PF_ADJUST), 4),
        "expectancy_threshold_adjust": round(_bounded(expr_adjust, MAX_EXPR_ADJUST), 4),
        "action": action,
    }


def load_recommendation(symbol: str, side: str) -> dict[str, Any] | None:
    if os.getenv("ENABLE_SIMULATION_RECOMMENDATIONS", "True").lower() not in {"1", "true", "yes"}:
        return None
    if not RECOMMENDATIONS_PATH.exists():
        return None
    try:
        payload = json.loads(RECOMMENDATIONS_PATH.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None
    key = f"{_clean_symbol(symbol)}:{_direction(side)}"
    rec = (payload.get("recommendations") or {}).get(key)
    if not rec or int(rec.get("samples", 0) or 0) < MIN_SAMPLES:
        return None
    return rec
