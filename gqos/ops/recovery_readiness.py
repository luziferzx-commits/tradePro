import json
import os
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5

from config.settings import settings
from gqos.ops.learning_insights import build_learning_coverage, build_live_sim_agreement
from gqos.ops.live_guard import get_daily_pnl
from gqos.ops.spread_guard import spread_status


STATE_PATH = Path(os.getenv("GQOS_RECOVERY_READINESS_PATH", "data/learning/recovery_readiness.json"))


def _enabled_symbols() -> list[str]:
    try:
        import yaml
        cfg = yaml.safe_load(Path("config/symbols.yaml").read_text(encoding="utf-8")) or {}
        return [symbol for symbol, data in (cfg.get("symbols") or {}).items() if data.get("enabled", False)]
    except Exception:
        return []


def _portfolio_paused_count(symbols: list[str]) -> int:
    try:
        from gqos.risk.portfolio_budget import portfolio_budget
    except Exception:
        return 0
    count = 0
    for symbol in symbols:
        try:
            if portfolio_budget.get_multiplier(symbol) <= 0:
                count += 1
        except Exception:
            continue
    return count


def build_recovery_readiness() -> dict[str, Any]:
    try:
        from gqos.ops.mt5_context import ensure_mt5_initialized
        ensure_mt5_initialized()
    except Exception:
        pass
    symbols = _enabled_symbols()
    spread_rows = [spread_status(symbol) for symbol in symbols]
    spread_ok = sum(1 for row in spread_rows if not row.get("blocked"))
    daily_pnl, trades, wins, losses = get_daily_pnl()
    coverage = build_learning_coverage()
    agreement = build_live_sim_agreement()
    paused = _portfolio_paused_count(symbols)
    open_positions = len(mt5.positions_get() or [])

    spread_score = spread_ok / len(symbols) if symbols else 0.0
    pnl_score = 1.0 if daily_pnl >= 0 else max(0.0, 1.0 + daily_pnl / 100.0)
    agreement_score = min(1.0, float(agreement.get("agreement_rate", 0.0) or 0.0) / 70.0)
    quality_score = min(1.0, float(coverage.get("new_quality", 0.0) or 0.0) / 90.0)
    pause_score = 1.0 - (paused / len(symbols) if symbols else 0.0)
    loss_pressure = losses / trades if trades else 0.0
    loss_score = max(0.0, 1.0 - loss_pressure)

    score = (
        spread_score * 0.25
        + pnl_score * 0.20
        + agreement_score * 0.20
        + quality_score * 0.20
        + pause_score * 0.10
        + loss_score * 0.05
    )

    agreement_ready = float(agreement.get("agreement_rate", 0.0) or 0.0) >= float(os.getenv("GQOS_RECOVERY_MIN_AGREEMENT_NORMAL", "60"))
    agreement_probe_ready = float(agreement.get("agreement_rate", 0.0) or 0.0) >= float(os.getenv("GQOS_RECOVERY_MIN_AGREEMENT_PROBE", "55"))

    if score >= 0.85 and daily_pnl >= 0 and spread_score >= 0.75 and agreement_ready:
        tier = "NORMAL_READY"
        probe_multiplier = 1.00
    elif score >= 0.72 and daily_pnl >= 0 and agreement_probe_ready:
        tier = "PROBE_025"
        probe_multiplier = 0.25
    elif score >= 0.60 and daily_pnl >= 0:
        tier = "PROBE_015"
        probe_multiplier = 0.15
    else:
        tier = "PROBE_008"
        probe_multiplier = float(settings.LIVE_GUARD_PROBE_MULTIPLIER)

    payload = {
        "score": round(score, 4),
        "tier": tier,
        "probe_multiplier": probe_multiplier,
        "spread_ok": spread_ok,
        "symbols": len(symbols),
        "daily_pnl": round(float(daily_pnl), 2),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "new_quality": round(float(coverage.get("new_quality", 0.0) or 0.0), 2),
        "agreement_rate": round(float(agreement.get("agreement_rate", 0.0) or 0.0), 2),
        "portfolio_paused": paused,
        "open_positions": open_positions,
    }
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def current_probe_multiplier() -> float:
    if os.getenv("ENABLE_AUTO_RELAX_PROBE", "True").lower() not in {"1", "true", "yes"}:
        return float(settings.LIVE_GUARD_PROBE_MULTIPLIER)
    return float(build_recovery_readiness().get("probe_multiplier", settings.LIVE_GUARD_PROBE_MULTIPLIER))


def build_recovery_readiness_report() -> str:
    data = build_recovery_readiness()
    return "\n".join([
        "Recovery Readiness",
        f"Score: {data['score']:.0%} | Tier: {data['tier']} | Probe: {data['probe_multiplier']:.2f}x",
        f"Spread OK: {data['spread_ok']}/{data['symbols']}",
        f"Today: {data['daily_pnl']:+.2f} USD | {data['trades']} trades ({data['wins']}W/{data['losses']}L)",
        f"New quality: {data['new_quality']:.0f}% | Live/Sim agreement: {data['agreement_rate']:.0f}%",
        f"Portfolio paused: {data['portfolio_paused']} | Open positions: {data['open_positions']}",
    ])
