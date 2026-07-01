import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SYSTEM_EVENTS_PATH = Path(os.getenv("GQOS_SYSTEM_EVENTS_FILE", "data/learning/system_events.jsonl"))
OUTCOMES_PATH = Path(os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl"))
MISSED_OUTCOMES_PATH = Path(os.getenv("GQOS_MISSED_OUTCOMES_PATH", "data/learning/missed_opportunity_outcomes.jsonl"))


PA_CATEGORIES = {
    "H4_TREND": ["MTF H4 Trend Conflict"],
    "H4_SR": ["Hit H4 S/R Wall", "H4 S/R Wall"],
    "H1_SR": ["H1 S/R Proximity"],
    "FVG": ["FVG Smart Money Align"],
    "LIQUIDITY": ["Liquidity Sweep"],
    "DIVERGENCE": ["H4 Momentum Divergence", "H4 Divergence"],
    "CHOP": ["CHOP"],
    "VOLUME": ["Dry Breakout"],
    "KILLZONE": ["killzone"],
    "USD": ["USD Basket Conflict"],
}


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


def _is_win(outcome: Any) -> bool:
    value = str(outcome or "").upper()
    return value.startswith("WIN") or value.startswith("TIMEOUT_WIN")


def _category_from_text(*parts: Any) -> str:
    text = " | ".join(str(part or "") for part in parts)
    for category, needles in PA_CATEGORIES.items():
        if any(needle in text for needle in needles):
            return category
    return "OTHER"


def _category_from_context(row: dict[str, Any]) -> list[str]:
    cats = []
    if row.get("pa_liquidity_sweep") and row.get("pa_liquidity_sweep") != "NONE":
        cats.append("LIQUIDITY")
    if row.get("pa_h4_divergence") and row.get("pa_h4_divergence") != "NONE":
        cats.append("DIVERGENCE")
    if row.get("pa_fvg_aligned") is True:
        cats.append("FVG")
    if row.get("pa_h1_chop") not in (None, "", "None"):
        try:
            if float(row.get("pa_h1_chop")) > float(os.getenv("PA_CHOP_THRESHOLD", "61.8")):
                cats.append("CHOP")
        except Exception:
            pass
    if row.get("pa_killzone"):
        cats.append(f"KILLZONE:{row.get('pa_killzone')}")
    if row.get("pa_usd_basket_trend"):
        cats.append(f"USD:{row.get('pa_usd_basket_trend')}")
    if row.get("pa_h4_trend"):
        cats.append(f"H4:{row.get('pa_h4_trend')}")
    return cats or ["NO_PA_TAG"]


def build_pa_rejection_summary(limit: int = 5000) -> list[dict[str, Any]]:
    rows = _read_jsonl(SYSTEM_EVENTS_PATH, limit=limit)
    counts = Counter()
    symbol_counts: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        if row.get("event_type") not in {"SIGNAL_REJECTED", "SIGNAL_SKIPPED", "RISK_CHECK_BLOCKED"}:
            continue
        category = _category_from_text(row.get("reason"), row.get("decision_tree"), row.get("price_action_context"))
        if category == "OTHER":
            continue
        counts[category] += 1
        symbol_counts[category][_clean_symbol(row.get("symbol"))] += 1
    output = []
    for category, count in counts.most_common():
        top_symbols = ", ".join(f"{sym}:{n}" for sym, n in symbol_counts[category].most_common(4))
        output.append({"category": category, "count": count, "top_symbols": top_symbols})
    return output


def build_pa_outcome_scores(limit: int = 1000) -> list[dict[str, Any]]:
    rows = _read_jsonl(OUTCOMES_PATH, limit=limit)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for category in _category_from_context(row):
            if category == "NO_PA_TAG":
                continue
            grouped[category].append(row)
    output = []
    for category, vals in grouped.items():
        if not vals:
            continue
        wins = sum(1 for row in vals if _is_win(row.get("outcome")))
        avg_r = sum(float(row.get("actual_r") or 0.0) for row in vals) / len(vals)
        pnl = sum(float(row.get("realized_pnl") or 0.0) for row in vals)
        output.append({
            "category": category,
            "samples": len(vals),
            "win_rate": wins / len(vals),
            "avg_r": avg_r,
            "pnl": pnl,
        })
    return sorted(output, key=lambda row: (row["samples"], row["avg_r"]), reverse=True)


def build_pa_counterfactual_scores(limit: int = 5000) -> list[dict[str, Any]]:
    rows = _read_jsonl(MISSED_OUTCOMES_PATH, limit=limit)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        category = _category_from_text(row.get("reason"))
        if category == "OTHER":
            continue
        grouped[category].append(row)
    output = []
    for category, vals in grouped.items():
        wins = sum(1 for row in vals if _is_win(row.get("outcome")))
        avg_r = sum(float(row.get("actual_r") or 0.0) for row in vals) / len(vals)
        output.append({
            "category": category,
            "samples": len(vals),
            "would_win_rate": wins / len(vals),
            "avg_r": avg_r,
            "verdict": "FILTER_HELPED" if avg_r < 0 else ("FILTER_TOO_STRICT" if avg_r > 0.25 else "MIXED"),
        })
    return sorted(output, key=lambda row: row["samples"], reverse=True)


def build_pa_filter_report() -> str:
    rejections = build_pa_rejection_summary()
    outcomes = build_pa_outcome_scores()
    counter = build_pa_counterfactual_scores()
    lines = ["Price Action Filter Analytics"]
    lines.append("Top PA rejection pressure:")
    if rejections:
        for row in rejections[:8]:
            lines.append(f"- {row['category']}: {row['count']}x [{row['top_symbols']}]")
    else:
        lines.append("- no PA-specific rejections yet")
    lines.append("")
    lines.append("Live outcome score by PA context:")
    if outcomes:
        for row in outcomes[:8]:
            lines.append(
                f"- {row['category']}: WR={row['win_rate']:.0%} AvgR={row['avg_r']:+.2f} "
                f"PnL={row['pnl']:+.2f} N={row['samples']}"
            )
    else:
        lines.append("- no closed trades with PA tags yet")
    lines.append("")
    lines.append("Counterfactual rejected-signal test:")
    if counter:
        for row in counter[:8]:
            lines.append(
                f"- {row['category']}: {row['verdict']} wouldWR={row['would_win_rate']:.0%} "
                f"AvgR={row['avg_r']:+.2f} N={row['samples']}"
            )
    else:
        lines.append("- waiting for missed-opportunity outcomes")
    lines.append("")
    try:
        from gqos.ops.pa_filter_calibrator import build_pa_calibration_report
        lines.append(build_pa_calibration_report(limit=8))
    except Exception as exc:
        lines.append(f"PA Filter Auto-Calibration unavailable: {exc}")
    return "\n".join(lines)
