import json
import os
from pathlib import Path
from typing import Any

from gqos.ops.pa_filter_analytics import (
    PA_CATEGORIES,
    build_pa_counterfactual_scores,
    build_pa_outcome_scores,
    build_pa_rejection_summary,
)


CALIBRATION_PATH = Path(os.getenv("GQOS_PA_CALIBRATION_PATH", "data/learning/pa_filter_calibration.json"))


DEFAULT_ACTIONS = {
    "H4_TREND": "PENALTY",
    "H4_SR": "PENALTY",
    "H1_SR": "PENALTY",
    "LIQUIDITY": "REJECT",
    "DIVERGENCE": "PENALTY",
    "CHOP": "PENALTY",
    "VOLUME": "PENALTY",
    "KILLZONE": "PENALTY",
    "USD": "PENALTY",
}


def _setting_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() == "true"


def _setting_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


def _setting_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _base_category(value: Any) -> str:
    return str(value or "").split(":", 1)[0].upper()


def _confidence(samples: float, min_samples: int) -> float:
    if min_samples <= 0:
        return 1.0
    return max(0.0, min(1.0, samples / float(min_samples * 3)))


def _load_rows_by_category(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {}
    for row in rows:
        category = _base_category(row.get("category"))
        if category and category not in output:
            output[category] = row
    return output


def _recommend_action(
    category: str,
    default_action: str,
    counter_row: dict[str, Any] | None,
    outcome_row: dict[str, Any] | None,
) -> tuple[str, float, str]:
    min_samples = _setting_int("PA_CALIBRATION_MIN_SAMPLES", 40)
    strict_avg_r = _setting_float("PA_CALIBRATION_STRICT_AVG_R", -0.10)
    relax_avg_r = _setting_float("PA_CALIBRATION_RELAX_AVG_R", 0.20)
    ignore_avg_r = _setting_float("PA_CALIBRATION_IGNORE_AVG_R", 0.45)
    strict_wr = _setting_float("PA_CALIBRATION_STRICT_WIN_RATE", 0.45)
    relax_wr = _setting_float("PA_CALIBRATION_RELAX_WIN_RATE", 0.56)

    default_action = (default_action or DEFAULT_ACTIONS.get(category) or "PENALTY").upper()
    if not _setting_bool("ENABLE_PA_FILTER_AUTOCALIBRATION", True):
        return default_action, 0.0, "autocalibration disabled"

    counter_samples = float((counter_row or {}).get("samples") or 0.0)
    live_samples = float((outcome_row or {}).get("samples") or 0.0)
    total_samples = counter_samples + live_samples
    conf = _confidence(total_samples, min_samples)
    if total_samples < max(5, min_samples):
        return default_action, conf, f"need more samples ({int(total_samples)}/{min_samples})"

    counter_avg_r = float((counter_row or {}).get("avg_r") or 0.0)
    counter_wr = float((counter_row or {}).get("would_win_rate") or 0.0)
    live_avg_r = float((outcome_row or {}).get("avg_r") or 0.0)
    live_wr = float((outcome_row or {}).get("win_rate") or 0.0)

    if counter_samples >= min_samples:
        if counter_avg_r <= strict_avg_r or counter_wr <= strict_wr:
            return "REJECT", conf, f"blocked signals performed poorly AvgR={counter_avg_r:+.2f} WR={counter_wr:.0%}"
        if counter_avg_r >= ignore_avg_r and counter_wr >= relax_wr:
            return "IGNORE", conf, f"blocked signals look valuable AvgR={counter_avg_r:+.2f} WR={counter_wr:.0%}"
        if counter_avg_r >= relax_avg_r or counter_wr >= relax_wr:
            return "PENALTY", conf, f"blocked signals deserve softer treatment AvgR={counter_avg_r:+.2f} WR={counter_wr:.0%}"

    if live_samples >= min_samples:
        if live_avg_r <= strict_avg_r or live_wr <= strict_wr:
            return "REJECT", conf, f"live trades with this context underperform AvgR={live_avg_r:+.2f} WR={live_wr:.0%}"
        if live_avg_r >= relax_avg_r and live_wr >= relax_wr:
            return "PENALTY" if default_action == "REJECT" else "IGNORE", conf, (
                f"live trades with this context perform well AvgR={live_avg_r:+.2f} WR={live_wr:.0%}"
            )

    return default_action, conf, "mixed evidence; keep configured action"


def build_pa_filter_scorecard() -> list[dict[str, Any]]:
    rejections = _load_rows_by_category(build_pa_rejection_summary())
    outcomes = _load_rows_by_category(build_pa_outcome_scores())
    counter = _load_rows_by_category(build_pa_counterfactual_scores())
    categories = sorted(set(PA_CATEGORIES) | set(DEFAULT_ACTIONS) | set(rejections) | set(outcomes) | set(counter))
    rows = []
    for category in categories:
        default_action = DEFAULT_ACTIONS.get(category, "PENALTY")
        action, confidence, reason = _recommend_action(
            category,
            default_action,
            counter.get(category),
            outcomes.get(category),
        )
        rows.append({
            "category": category,
            "default_action": default_action,
            "recommended_action": action,
            "confidence": round(confidence, 3),
            "reason": reason,
            "rejections": int((rejections.get(category) or {}).get("count") or 0),
            "live_samples": int((outcomes.get(category) or {}).get("samples") or 0),
            "live_win_rate": round(float((outcomes.get(category) or {}).get("win_rate") or 0.0), 4),
            "live_avg_r": round(float((outcomes.get(category) or {}).get("avg_r") or 0.0), 4),
            "counterfactual_samples": int((counter.get(category) or {}).get("samples") or 0),
            "counterfactual_win_rate": round(float((counter.get(category) or {}).get("would_win_rate") or 0.0), 4),
            "counterfactual_avg_r": round(float((counter.get(category) or {}).get("avg_r") or 0.0), 4),
        })
    return sorted(rows, key=lambda row: (row["confidence"], row["rejections"]), reverse=True)


def refresh_pa_filter_calibration() -> list[dict[str, Any]]:
    rows = build_pa_filter_scorecard()
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(json.dumps({"scorecard": rows}, indent=2), encoding="utf-8")
    return rows


def _load_scorecard() -> list[dict[str, Any]]:
    if not CALIBRATION_PATH.exists():
        return refresh_pa_filter_calibration()
    ttl_seconds = _setting_int("PA_CALIBRATION_REFRESH_SECONDS", 300)
    try:
        if ttl_seconds > 0 and CALIBRATION_PATH.stat().st_mtime < (__import__("time").time() - ttl_seconds):
            return refresh_pa_filter_calibration()
    except Exception:
        pass
    try:
        payload = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8", errors="ignore"))
        rows = payload.get("scorecard") or []
        return rows if isinstance(rows, list) else []
    except Exception:
        return refresh_pa_filter_calibration()


def recommended_action(category: str, default_action: str = "PENALTY") -> str:
    category = _base_category(category)
    if not _setting_bool("ENABLE_PA_FILTER_AUTOCALIBRATION", True):
        return (default_action or "PENALTY").upper()
    min_conf = _setting_float("PA_CALIBRATION_MIN_CONFIDENCE", 0.25)
    for row in _load_scorecard():
        if _base_category(row.get("category")) == category:
            if float(row.get("confidence") or 0.0) < min_conf:
                return (default_action or row.get("default_action") or "PENALTY").upper()
            return str(row.get("recommended_action") or default_action or "PENALTY").upper()
    return (default_action or DEFAULT_ACTIONS.get(category) or "PENALTY").upper()


def build_pa_calibration_report(limit: int = 10) -> str:
    rows = refresh_pa_filter_calibration()
    lines = ["PA Filter Auto-Calibration"]
    for row in rows[:limit]:
        lines.append(
            f"- {row['category']}: {row['recommended_action']} "
            f"conf={row['confidence']:.0%} rej={row['rejections']} "
            f"liveR={row['live_avg_r']:+.2f}/{row['live_samples']} "
            f"missR={row['counterfactual_avg_r']:+.2f}/{row['counterfactual_samples']} "
            f"({row['reason']})"
        )
    return "\n".join(lines)
