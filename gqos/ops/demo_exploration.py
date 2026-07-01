import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5

from config.settings import settings

logger = logging.getLogger(__name__)

RECOMMENDATIONS_PATH = Path(os.getenv("GQOS_SIM_RECOMMENDATIONS_PATH", "data/learning/simulation_recommendations.json"))
LIVE_OUTCOMES_PATH = Path(os.getenv("GQOS_LIVE_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl"))
PENDING_TRADES_PATH = Path(os.getenv("GQOS_PENDING_TRADES_PATH", "data/learning/pending_trades.json"))


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


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_today(value: Any) -> bool:
    dt = _parse_ts(value)
    if not dt:
        return False
    return dt.date() == datetime.now(timezone.utc).date()


def _count_today_explore() -> int:
    count = 0
    if LIVE_OUTCOMES_PATH.exists():
        with LIVE_OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("entry_mode") or "").upper() == "EXPLORE" and _is_today(row.get("open_time") or row.get("close_time")):
                    count += 1

    if PENDING_TRADES_PATH.exists():
        try:
            pending = json.loads(PENDING_TRADES_PATH.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pending = {}
        for row in pending.values() if isinstance(pending, dict) else []:
            if isinstance(row, dict) and str(row.get("entry_mode") or "").upper() == "EXPLORE" and _is_today(row.get("open_time")):
                count += 1
    return count


def _load_recommendations() -> dict[str, Any]:
    try:
        from gqos.learning.simulation_analyzer import build_simulation_recommendations
        return build_simulation_recommendations()
    except Exception as exc:
        logger.warning("[DemoExplore] Could not rebuild simulation recommendations: %s", exc)
    if not RECOMMENDATIONS_PATH.exists():
        return {}
    try:
        return json.loads(RECOMMENDATIONS_PATH.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _passes_recommendation(rec: dict[str, Any]) -> bool:
    confidence = float(rec.get("confidence") or 0.0)
    avg_r = float(rec.get("avg_r") or 0.0)
    win_rate = float(rec.get("win_rate") or 0.0)
    action = str(rec.get("action") or "").upper()
    soft_rule = str(rec.get("soft_rule") or "").upper()
    if "BLACKLIST" in soft_rule:
        return False
    if confidence < settings.DEMO_EXPLORATION_MIN_CONFIDENCE:
        return False
    if action == "RELAX_SLIGHTLY" or "WHITELIST" in soft_rule:
        return True
    if avg_r >= settings.DEMO_EXPLORATION_MIN_AVG_R and win_rate >= settings.DEMO_EXPLORATION_MIN_WIN_RATE:
        return True
    return bool(settings.DEMO_EXPLORATION_ALLOW_NEUTRAL and avg_r >= 0.0 and win_rate >= 0.50)


def _score(rec: dict[str, Any]) -> float:
    confidence = float(rec.get("confidence") or 0.0)
    avg_r = float(rec.get("avg_r") or 0.0)
    win_rate = float(rec.get("win_rate") or 0.0)
    samples = min(float(rec.get("samples") or 0.0), 300.0) / 300.0
    return (avg_r * 1.25) + ((win_rate - 0.50) * 1.00) + (confidence * 0.35) + (samples * 0.15)


def build_demo_exploration_candidates(registry, mt5_client, approved_signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not settings.ENABLE_DEMO_EXPLORATION:
        return []

    target = max(0, int(settings.DEMO_EXPLORATION_TARGET_SIGNALS_PER_SCAN))
    if len(approved_signals) >= target:
        return []

    remaining_daily = max(0, int(settings.DEMO_EXPLORATION_DAILY_CAP) - _count_today_explore())
    if remaining_daily <= 0:
        logger.info("[DemoExplore] Daily cap reached; no exploration candidates.")
        return []

    slots = min(int(settings.DEMO_EXPLORATION_MAX_PER_SCAN), target - len(approved_signals), remaining_daily)
    if slots <= 0:
        return []

    payload = _load_recommendations()
    recommendations = list((payload.get("recommendations") or {}).values())
    if not recommendations:
        return []

    enabled = {_clean_symbol(row.get("symbol")) for row in registry.get_enabled_symbols()}
    already = {_clean_symbol(sig.get("symbol")) for sig in approved_signals}
    candidates = []
    for rec in recommendations:
        symbol = _clean_symbol(rec.get("symbol"))
        side = str(rec.get("side") or "").upper()
        if symbol not in enabled or symbol in already or side not in {"LONG", "SHORT"}:
            continue
        if not _passes_recommendation(rec):
            continue

        try:
            from gqos.ops.spread_guard import should_skip_for_spread
            skip, reason, spread_meta = should_skip_for_spread(symbol)
            if skip:
                logger.info("[DemoExplore] %s skipped: %s", symbol, reason)
                continue
        except Exception as exc:
            logger.warning("[DemoExplore] Spread check failed for %s: %s", symbol, exc)
            spread_meta = {}

        resolved = mt5_client.resolve_symbol(symbol)
        if mt5.positions_get(symbol=resolved) or mt5.orders_get(symbol=resolved):
            continue

        try:
            from strategy.indicators import IndicatorCalculator
            df = mt5_client.get_historical_data(symbol, "M15", 250)
            if df is None or df.empty:
                continue
            df = IndicatorCalculator.add_indicators(df)
            atr = float(df.iloc[-1].get("atr") or 0.0)
        except Exception as exc:
            logger.info("[DemoExplore] Could not prepare %s: %s", symbol, exc)
            continue

        direction = "BUY" if side == "LONG" else "SELL"
        candidates.append({
            "symbol": symbol,
            "side": direction,
            "model_probability": min(0.90, max(0.55, float(rec.get("confidence") or 0.55))),
            "atr": atr,
            "source": "DEMO_EXPLORATION",
            "metadata": {
                "simulation_recommendation": rec,
                "simulation_action": rec.get("action"),
                "simulation_soft_rule": rec.get("soft_rule"),
                "simulation_confidence": rec.get("confidence"),
                "simulation_avg_r": rec.get("avg_r"),
                "simulation_win_rate": rec.get("win_rate"),
                "simulation_samples": rec.get("samples"),
                "entry_mode_override": "EXPLORE",
                "probe_reason": "demo exploration from simulation recommendation",
                "exploration_exception": "bypass_pa_soft_filters_for_learning; risk_and_spread_guards_still_apply",
                "spread": spread_meta.get("spread"),
                "spread_ratio": spread_meta.get("ratio"),
            },
            "reason": (
                f"Demo exploration: {symbol} {side} "
                f"AvgR={float(rec.get('avg_r') or 0.0):+.2f} "
                f"WR={float(rec.get('win_rate') or 0.0):.0%} "
                f"Conf={float(rec.get('confidence') or 0.0):.0%}"
            ),
            "_explore_score": _score(rec),
        })

    candidates.sort(key=lambda row: row.get("_explore_score", 0.0), reverse=True)
    selected = candidates[:slots]
    for row in selected:
        row.pop("_explore_score", None)
        logger.warning("[DemoExplore] Selected %s %s: %s", row["symbol"], row["side"], row.get("reason"))
    return selected
