import json
import os
from collections import defaultdict
from pathlib import Path


OBS_PATH = Path(os.getenv("GQOS_MARKET_OBSERVATIONS_PATH", "data/learning/market_observations.jsonl"))
PENDING_PATH = Path(os.getenv("GQOS_VIRTUAL_PENDING_PATH", "data/learning/virtual_trades.json"))
OUTCOMES_PATH = Path(os.getenv("GQOS_VIRTUAL_OUTCOMES_PATH", "data/learning/virtual_trade_outcomes.jsonl"))


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.open("r", encoding="utf-8", errors="ignore") if line.strip())


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def _read_outcomes(limit: int = 20000) -> list[dict]:
    if not OUTCOMES_PATH.exists():
        return []
    rows = []
    with OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
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


def build_continuous_market_sim_report() -> str:
    pending = _read_json(PENDING_PATH, {})
    outcomes = _read_outcomes()
    observations = _jsonl_count(OBS_PATH)

    total = len(outcomes)
    wins = sum(1 for row in outcomes if str(row.get("outcome", "")).startswith("WIN") or str(row.get("outcome", "")).startswith("TIMEOUT_WIN"))
    losses = sum(1 for row in outcomes if "LOSS" in str(row.get("outcome", "")))
    win_rate = wins / total * 100 if total else 0.0
    avg_r = sum(float(row.get("actual_r") or 0.0) for row in outcomes) / total if total else 0.0

    by_symbol = defaultdict(list)
    by_detail = defaultdict(list)
    by_regime = defaultdict(list)
    by_market_session = defaultdict(list)
    for row in outcomes:
        actual_r = float(row.get("actual_r") or 0.0)
        symbol = str(row.get("symbol") or "UNKNOWN")
        side = str(row.get("side") or "UNKNOWN")
        session = str(row.get("session") or "UNKNOWN")
        market_session = str(row.get("market_session") or "UNKNOWN")
        spread_bucket = str(row.get("spread_bucket") or "UNKNOWN")
        vol_bucket = str(row.get("volatility_bucket") or "UNKNOWN")
        by_symbol[symbol].append(actual_r)
        by_detail[(symbol, side, session)].append(actual_r)
        by_market_session[(symbol, side, market_session)].append(actual_r)
        by_regime[(spread_bucket, vol_bucket)].append(actual_r)
    top = sorted(
        ((symbol, len(vals), sum(vals) / len(vals)) for symbol, vals in by_symbol.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:10]
    detail_top = sorted(
        ((key, len(vals), sum(vals) / len(vals)) for key, vals in by_detail.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:10]
    regime_top = sorted(
        ((key, len(vals), sum(vals) / len(vals)) for key, vals in by_regime.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:8]
    market_session_top = sorted(
        ((key, len(vals), sum(vals) / len(vals)) for key, vals in by_market_session.items()),
        key=lambda item: item[2],
        reverse=True,
    )[:10]

    lines = [
        "Continuous Market Simulation",
        f"M1 observations: {observations}",
        f"Open virtual trades: {len(pending) if isinstance(pending, dict) else 0}",
        f"Closed virtual trades: {total}",
        f"Virtual win rate: {win_rate:.1f}% ({wins}W/{losses}L)",
        f"Average virtual R: {avg_r:+.2f}",
    ]
    if top:
        lines.append("")
        lines.append("Top symbols by virtual avg R:")
        lines.extend(f"- {symbol}: {avg_r_sym:+.2f}R over {count}" for symbol, count, avg_r_sym in top)
    if detail_top:
        lines.append("")
        lines.append("Top symbol/side/session:")
        lines.extend(
            f"- {symbol} {side} {session}: {avg_r_group:+.2f}R over {count}"
            for (symbol, side, session), count, avg_r_group in detail_top
        )
    if regime_top:
        lines.append("")
        lines.append("Top spread/volatility buckets:")
        lines.extend(
            f"- spread={spread_bucket} vol={vol_bucket}: {avg_r_group:+.2f}R over {count}"
            for (spread_bucket, vol_bucket), count, avg_r_group in regime_top
        )
    if market_session_top:
        lines.append("")
        lines.append("Top market-specific sessions:")
        lines.extend(
            f"- {symbol} {side} {market_session}: {avg_r_group:+.2f}R over {count}"
            for (symbol, side, market_session), count, avg_r_group in market_session_top
        )
    return "\n".join(lines)
