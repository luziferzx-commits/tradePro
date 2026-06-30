import json
import os
from collections import Counter, defaultdict
from pathlib import Path


PENDING_PATH = Path(os.getenv("GQOS_MISSED_PENDING_PATH", "data/learning/missed_opportunities.json"))
OUTCOMES_PATH = Path(os.getenv("GQOS_MISSED_OUTCOMES_PATH", "data/learning/missed_opportunity_outcomes.jsonl"))


def _read_pending() -> dict:
    if not PENDING_PATH.exists():
        return {}
    try:
        data = json.loads(PENDING_PATH.read_text(encoding="utf-8", errors="ignore"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_outcomes() -> list[dict]:
    rows = []
    if not OUTCOMES_PATH.exists():
        return rows
    with OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_missed_opportunity_report(max_reasons: int = 8) -> str:
    pending = _read_pending()
    outcomes = _read_outcomes()
    wins = [r for r in outcomes if str(r.get("outcome", "")).startswith("WIN") or str(r.get("outcome", "")).startswith("TIMEOUT_WIN")]
    losses = [r for r in outcomes if "LOSS" in str(r.get("outcome", ""))]
    total = len(outcomes)
    win_rate = len(wins) / total * 100 if total else 0.0
    avg_r = sum(float(r.get("actual_r") or 0.0) for r in outcomes) / total if total else 0.0

    reason_counts = Counter(str(r.get("reason") or "UNKNOWN") for r in outcomes)
    symbol_r = defaultdict(list)
    for row in outcomes:
        symbol_r[str(row.get("symbol") or "UNKNOWN")].append(float(row.get("actual_r") or 0.0))
    top_symbols = sorted(
        ((symbol, len(vals), sum(vals) / len(vals)) for symbol, vals in symbol_r.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:8]

    lines = [
        "Missed Opportunity Tracker",
        f"Pending simulations: {len(pending)}",
        f"Closed simulations: {total}",
        f"Would-win rate: {win_rate:.1f}% ({len(wins)}W/{len(losses)}L)",
        f"Average simulated R: {avg_r:+.2f}",
    ]
    if top_symbols:
        lines.append("")
        lines.append("Top simulated symbols by avg R:")
        lines.extend(f"- {symbol}: {avg_r_sym:+.2f}R over {count}" for symbol, count, avg_r_sym in top_symbols)
    if reason_counts:
        lines.append("")
        lines.append("Top blocked/rejected reasons tested:")
        lines.extend(f"- {count}x {reason[:90]}" for reason, count in reason_counts.most_common(max_reasons))
    return "\n".join(lines)
