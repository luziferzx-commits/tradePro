import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


OUTCOMES_PATH = Path(os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl"))
SYSTEM_EVENTS_PATH = Path(os.getenv("GQOS_SYSTEM_EVENTS_FILE", "data/learning/system_events.jsonl"))
SIM_RECOMMENDATIONS_PATH = Path(os.getenv("GQOS_SIM_RECOMMENDATIONS_PATH", "data/learning/simulation_recommendations.json"))


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
                if limit and len(rows) > limit:
                    rows.pop(0)
            except json.JSONDecodeError:
                continue
    return rows


def _clean_symbol(symbol: Any) -> str:
    value = str(symbol or "").upper()
    for suffix in (".M", "M"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    if value == "USTEC":
        return "NAS100"
    if value == "DE30":
        return "GER40"
    return value


def _side(value: Any) -> str:
    text = str(value or "").upper()
    if "BUY" in text or "LONG" in text:
        return "LONG"
    if "SELL" in text or "SHORT" in text:
        return "SHORT"
    return text or "UNKNOWN"


def _session(value: Any) -> str:
    text = str(value or "UNKNOWN").upper()
    invalid = {
        "MT5_HISTORY",
        "RESEARCH_VALIDATED",
        "RESEARCH_DISCOVERED",
        "SHADOW_PASSED",
        "LIVE_APPROVED",
        "REJECTED",
        "UNKNOWN",
        "",
    }
    if text in invalid:
        return "UNKNOWN"
    return str(value)


def _sim_key(symbol: Any, side: Any) -> str:
    return f"{_clean_symbol(symbol)}:{_side(side)}"


def load_sim_recommendations() -> dict[str, Any]:
    payload = _read_json(SIM_RECOMMENDATIONS_PATH, {})
    return payload if isinstance(payload, dict) else {}


def build_learning_coverage() -> dict[str, Any]:
    outcomes = _read_jsonl(OUTCOMES_PATH)
    total = len(outcomes)
    new_outcomes = [row for row in outcomes if row.get("sync_source") != "mt5_history_backfill"]
    new_total = len(new_outcomes)
    fields = [
        "pattern_id",
        "session",
        "strategy_id",
        "decision_id",
        "entry_mode",
        "source",
        "run_id",
        "account_id",
    ]
    coverage = {}
    for field in fields:
        coverage[field] = sum(1 for row in outcomes if row.get(field))
    tagged = sum(1 for row in outcomes if row.get("pattern_id"))
    new_tagged = sum(1 for row in new_outcomes if row.get("pattern_id"))
    backfilled = sum(1 for row in outcomes if row.get("sync_source") == "mt5_history_backfill")
    return {
        "total": total,
        "tagged": tagged,
        "quality": (tagged / total * 100.0) if total else 0.0,
        "new_total": new_total,
        "new_tagged": new_tagged,
        "new_quality": (new_tagged / new_total * 100.0) if new_total else 0.0,
        "backfilled": backfilled,
        "coverage": coverage,
    }


def build_live_sim_agreement(limit: int = 200) -> dict[str, Any]:
    outcomes = _read_jsonl(OUTCOMES_PATH, limit=limit)
    recs = (load_sim_recommendations().get("recommendations") or {})
    rows = []
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"agree": 0, "disagree": 0, "neutral": 0})
    agree = 0
    disagree = 0
    neutral = 0
    for row in outcomes:
        key = _sim_key(row.get("symbol"), row.get("direction"))
        rec = recs.get(key)
        if not rec:
            continue
        outcome = str(row.get("outcome") or "").upper()
        soft_rule = str(rec.get("soft_rule") or rec.get("action") or "NEUTRAL")
        live_win = outcome == "WIN"
        if "WHITELIST" in soft_rule or rec.get("action") == "RELAX_SLIGHTLY":
            verdict = "AGREE" if live_win else "DISAGREE"
        elif "BLACKLIST" in soft_rule or rec.get("action") == "TIGHTEN_SLIGHTLY":
            verdict = "AGREE" if not live_win else "DISAGREE"
        else:
            verdict = "NEUTRAL"
        if verdict == "AGREE":
            agree += 1
        elif verdict == "DISAGREE":
            disagree += 1
        else:
            neutral += 1
        rows.append({
            "symbol": _clean_symbol(row.get("symbol")),
            "side": _side(row.get("direction")),
            "session": _session(row.get("session")),
            "outcome": outcome,
            "actual_r": row.get("actual_r"),
            "sim_action": rec.get("action"),
            "soft_rule": rec.get("soft_rule"),
            "sim_confidence": rec.get("confidence"),
            "sim_avg_r": rec.get("avg_r"),
            "verdict": verdict,
        })
        group_key = (_clean_symbol(row.get("symbol")), _side(row.get("direction")), _session(row.get("session")))
        if group_key[2] != "UNKNOWN":
            grouped[group_key][verdict.lower()] += 1
    scored = agree + disagree
    context_rows = []
    for (symbol, side, session), counts in grouped.items():
        scored_context = counts["agree"] + counts["disagree"]
        if scored_context <= 0:
            continue
        context_rows.append({
            "symbol": symbol,
            "side": side,
            "session": session,
            "agree": counts["agree"],
            "disagree": counts["disagree"],
            "neutral": counts["neutral"],
            "agreement_rate": counts["agree"] / scored_context * 100.0,
            "samples": scored_context + counts["neutral"],
        })
    return {
        "agree": agree,
        "disagree": disagree,
        "neutral": neutral,
        "agreement_rate": (agree / scored * 100.0) if scored else 0.0,
        "rows": rows[-50:],
        "context_rows": sorted(context_rows, key=lambda row: (row["samples"], row["agreement_rate"]), reverse=True),
    }


def build_session_scores(min_samples: int = 3) -> list[dict[str, Any]]:
    outcomes = _read_jsonl(OUTCOMES_PATH)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in outcomes:
        grouped[(
            _clean_symbol(row.get("symbol")),
            _side(row.get("direction")),
            _session(row.get("session")),
        )].append(row)
    rows = []
    for (symbol, side, session), vals in grouped.items():
        if session == "UNKNOWN" or len(vals) < min_samples:
            continue
        wins = sum(1 for row in vals if row.get("outcome") == "WIN")
        pnl = sum(float(row.get("realized_pnl") or 0.0) for row in vals)
        rs = [float(row.get("actual_r") or 0.0) for row in vals if row.get("actual_r") is not None]
        avg_r = sum(rs) / len(rs) if rs else 0.0
        score = avg_r * 0.65 + ((wins / len(vals)) - 0.5) * 0.70
        rows.append({
            "symbol": symbol,
            "side": side,
            "session": session,
            "samples": len(vals),
            "win_rate": wins / len(vals),
            "avg_r": avg_r,
            "pnl": pnl,
            "score": score,
            "label": "GOOD" if score > 0.25 else ("AVOID" if score < -0.25 else "WATCH"),
        })
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def build_why_table(limit: int = 800) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for event in _read_jsonl(SYSTEM_EVENTS_PATH, limit=limit):
        if event.get("event_type") not in {
            "SIGNAL_EVALUATED",
            "SIGNAL_REJECTED",
            "SIGNAL_APPROVED",
            "SIGNAL_SKIPPED",
            "RISK_CHECK_PASSED",
            "RISK_CHECK_BLOCKED",
            "ORDER_REJECTED",
            "ORDER_FILLED",
        }:
            continue
        key = (_clean_symbol(event.get("symbol")), _side(event.get("side")))
        if key[0]:
            latest[key] = event
    rows = []
    recs = (load_sim_recommendations().get("recommendations") or {})
    for (symbol, side), event in sorted(latest.items()):
        rec = recs.get(f"{symbol}:{side}") or {}
        rows.append({
            "symbol": symbol,
            "side": side,
            "status": event.get("status") or event.get("event_type"),
            "reason": event.get("reason", ""),
            "pf": event.get("profit_factor"),
            "expectancy_r": event.get("expectancy_r"),
            "similarity": event.get("similarity"),
            "sim_action": rec.get("action"),
            "soft_rule": rec.get("soft_rule"),
            "sim_confidence": rec.get("confidence"),
            "sim_avg_r": rec.get("avg_r"),
            "pa_h4_trend": (event.get("price_action_context") or {}).get("h4_trend") if isinstance(event.get("price_action_context"), dict) else event.get("pa_h4_trend"),
            "pa_divergence": (event.get("price_action_context") or {}).get("h4_divergence") if isinstance(event.get("price_action_context"), dict) else event.get("pa_h4_divergence"),
            "pa_sweep": (event.get("price_action_context") or {}).get("liquidity_sweep") if isinstance(event.get("price_action_context"), dict) else event.get("pa_liquidity_sweep"),
            "ts": event.get("ts"),
        })
    return rows


def build_learning_insights_report() -> str:
    coverage = build_learning_coverage()
    agreement = build_live_sim_agreement()
    sessions = build_session_scores()
    why = build_why_table()
    lines = [
        "Learning Insights",
        f"Quality: {coverage['quality']:.0f}% ({coverage['tagged']}/{coverage['total']} tagged), "
        f"new={coverage['new_quality']:.0f}% ({coverage['new_tagged']}/{coverage['new_total']}), "
        f"backfilled={coverage['backfilled']}",
        f"Live/Sim Agreement: {agreement['agreement_rate']:.0f}% ({agreement['agree']} agree / {agreement['disagree']} disagree / {agreement['neutral']} neutral)",
        "",
        "Top live session scores:",
    ]
    for row in sessions[:5]:
        lines.append(
            f"- {row['symbol']} {row['side']} {row['session']}: {row['label']} "
            f"WR={row['win_rate']:.0%} AvgR={row['avg_r']:+.2f} N={row['samples']}"
        )
    if agreement.get("context_rows"):
        lines.append("")
        lines.append("Top live/sim context agreement:")
        for row in agreement["context_rows"][:5]:
            lines.append(
                f"- {row['symbol']} {row['side']} {row['session']}: "
                f"{row['agreement_rate']:.0f}% agree N={row['samples']}"
            )
    lines.append("")
    lines.append("Recent why table:")
    for row in why[:10]:
        lines.append(
            f"- {row['symbol']} {row['side']} {row['status']}: {row['reason']} "
            f"Sim={row.get('soft_rule') or row.get('sim_action') or 'NA'}"
        )
    return "\n".join(lines)
