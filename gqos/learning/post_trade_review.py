import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEWS_PATH = Path(os.getenv("GQOS_POST_TRADE_REVIEWS_PATH", "data/learning/post_trade_reviews.jsonl"))


def _verdict(record: dict[str, Any]) -> str:
    outcome = str(record.get("outcome") or "").upper()
    soft_rule = str(record.get("simulation_soft_rule") or "")
    action = str(record.get("simulation_action") or "")
    live_win = outcome == "WIN"
    if "WHITELIST" in soft_rule or action == "RELAX_SLIGHTLY":
        return "SIM_AGREED" if live_win else "SIM_DISAGREED"
    if "BLACKLIST" in soft_rule or action == "TIGHTEN_SLIGHTLY":
        return "SIM_AGREED" if not live_win else "SIM_DISAGREED"
    return "SIM_NEUTRAL"


def write_post_trade_review(record: dict[str, Any]) -> dict[str, Any]:
    review = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "decision_id": record.get("decision_id"),
        "ticket": record.get("ticket"),
        "symbol": record.get("symbol"),
        "direction": record.get("direction"),
        "session": record.get("session"),
        "regime": record.get("regime"),
        "atr_bucket": record.get("atr_bucket"),
        "entry_mode": record.get("entry_mode"),
        "pattern_id": record.get("pattern_id"),
        "pattern_pf": record.get("pattern_pf"),
        "pattern_similarity": record.get("pattern_similarity"),
        "expectancy_r": record.get("expectancy_r"),
        "simulation_action": record.get("simulation_action"),
        "simulation_soft_rule": record.get("simulation_soft_rule"),
        "simulation_confidence": record.get("simulation_confidence"),
        "simulation_avg_r": record.get("simulation_avg_r"),
        "pa_h4_trend": record.get("pa_h4_trend"),
        "pa_h4_divergence": record.get("pa_h4_divergence"),
        "pa_liquidity_sweep": record.get("pa_liquidity_sweep"),
        "pa_fvg_aligned": record.get("pa_fvg_aligned"),
        "pa_h1_chop": record.get("pa_h1_chop"),
        "pa_killzone": record.get("pa_killzone"),
        "pa_usd_basket_trend": record.get("pa_usd_basket_trend"),
        "outcome": record.get("outcome"),
        "actual_r": record.get("actual_r"),
        "realized_pnl": record.get("realized_pnl"),
        "review_verdict": _verdict(record),
    }
    REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REVIEWS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(review) + "\n")
    return review


def build_post_trade_review_report(limit: int = 10) -> str:
    if not REVIEWS_PATH.exists():
        return "Post-Trade Review\nNo reviews recorded yet."
    rows = []
    with REVIEWS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return "Post-Trade Review\nNo reviews recorded yet."
    recent = rows[-limit:]
    agreed = sum(1 for row in rows if row.get("review_verdict") == "SIM_AGREED")
    disagreed = sum(1 for row in rows if row.get("review_verdict") == "SIM_DISAGREED")
    lines = [
        "Post-Trade Review",
        f"Sim agreement on reviewed trades: {agreed}/{agreed + disagreed}" if agreed + disagreed else "Sim agreement: no scored reviews yet",
    ]
    for row in recent:
        lines.append(
            f"- {row.get('symbol')} {row.get('direction')} {row.get('outcome')} "
            f"R={float(row.get('actual_r') or 0.0):+.2f} {row.get('review_verdict')}"
        )
    return "\n".join(lines)
