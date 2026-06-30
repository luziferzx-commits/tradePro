import json
import os
from pathlib import Path


OUTCOMES_PATH = Path(os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl"))
PENDING_PATH = Path(os.getenv("GQOS_PENDING_TRADES_PATH", "data/learning/pending_trades.json"))
RETRAIN_STATE_PATH = Path(os.getenv("GQOS_RETRAIN_STATE_PATH", "data/learning/retrain_state.json"))
RETRAIN_THRESHOLD = int(os.getenv("GQOS_RETRAIN_THRESHOLD", "50"))


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def build_learning_health() -> tuple[bool, str]:
    outcomes = _read_jsonl(OUTCOMES_PATH)
    pending = _read_json(PENDING_PATH, {})
    retrain = _read_json(RETRAIN_STATE_PATH, {})

    pending_values = [v for v in pending.values()] if isinstance(pending, dict) else []
    pending_with_pattern = sum(1 for v in pending_values if isinstance(v, dict) and v.get("pattern_id"))
    outcomes_with_pattern = sum(1 for row in outcomes if row.get("pattern_id"))
    backfilled = sum(1 for row in outcomes if row.get("sync_source") == "mt5_history_backfill")
    wins = sum(1 for row in outcomes if row.get("outcome") == "WIN")
    losses = sum(1 for row in outcomes if row.get("outcome") == "LOSS")
    pnl = sum(float(row.get("realized_pnl") or 0.0) for row in outcomes)
    normal = sum(1 for row in outcomes if (row.get("entry_mode") or "NORMAL") == "NORMAL")
    probes = len(outcomes) - normal

    total = len(outcomes)
    pattern_ratio = (outcomes_with_pattern / total) if total else 0.0
    next_retrain = max(0, RETRAIN_THRESHOLD - int(retrain.get("trades_since_retrain", 0) or 0))

    issues = []
    if total == 0:
        issues.append("No closed outcomes recorded yet.")
    if total and pattern_ratio < 0.5:
        issues.append("Most closed outcomes are missing pattern_id; old MT5 backfills cannot fully train pattern-level edge.")
    if pending_values and pending_with_pattern < len(pending_values):
        issues.append("Some pending trades are missing pattern metadata.")
    if pending_with_pattern == 0:
        issues.append("No active pending trade has pattern metadata.")

    ok = not issues
    lines = [
        "GQOS Learning Health",
        f"Status: {'PASS' if ok else 'CHECK'}",
        f"Closed outcomes: {total}",
        f"Outcomes with pattern: {outcomes_with_pattern}/{total} ({pattern_ratio:.0%})",
        f"MT5 backfilled outcomes: {backfilled}",
        f"Pending trades with pattern: {pending_with_pattern}/{len(pending_values)}",
        f"Normal/probe outcomes: {normal}/{probes}",
        f"Win/Loss: {wins}/{losses}",
        f"Recorded PnL: {pnl:+.2f}",
        f"Retrain progress: {retrain.get('trades_since_retrain', 0)}/{RETRAIN_THRESHOLD}",
        f"Next retrain in: {next_retrain}",
    ]
    if issues:
        lines.append("")
        lines.append("Issues:")
        lines.extend(f"- {issue}" for issue in issues)
    return ok, "\n".join(lines)
