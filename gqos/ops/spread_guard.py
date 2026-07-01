import os
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import yaml


SYMBOLS_PATH = Path("config/symbols.yaml")


def _load_config() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    try:
        cfg = yaml.safe_load(SYMBOLS_PATH.read_text(encoding="utf-8")) or {}
        return cfg.get("symbols", {}) or {}, cfg.get("symbol_aliases", {}) or {}
    except Exception:
        return {}, {}


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


def spread_status(symbol: str) -> dict[str, Any]:
    try:
        from gqos.ops.mt5_context import ensure_mt5_initialized
        ensure_mt5_initialized()
    except Exception:
        pass
    symbols, aliases = _load_config()
    clean = _clean_symbol(symbol)
    broker = aliases.get(clean, symbol)
    cfg = symbols.get(clean, {})
    info = mt5.symbol_info(broker)
    spread = getattr(info, "spread", None) if info else None
    max_spread = cfg.get("max_spread_points")
    typical = float(cfg.get("typical_spread_points", 0) or 0)
    ratio = (float(spread) / typical) if spread is not None and typical > 0 else None
    max_ratio = float(os.getenv("GQOS_SPREAD_AVOID_RATIO", "3.0"))
    enabled = os.getenv("ENABLE_SPREAD_AVOIDANCE", "True").lower() in {"1", "true", "yes"}
    blocked = False
    reason = ""
    if enabled:
        if max_spread is not None and spread is not None and float(spread) > float(max_spread):
            blocked = True
            reason = f"Spread too wide: {spread}>{max_spread}"
        elif ratio is not None and ratio >= max_ratio:
            blocked = True
            reason = f"Spread ratio too wide: {ratio:.1f}x typical"
    try:
        from gqos.ops.spread_regime_memory import is_do_not_trade_window
        regime_blocked, regime_reason = is_do_not_trade_window(clean)
        if regime_blocked:
            blocked = True
            reason = regime_reason
    except Exception:
        pass
    return {
        "symbol": clean,
        "broker": broker,
        "spread": spread,
        "max_spread": max_spread,
        "typical_spread": typical,
        "ratio": ratio,
        "blocked": blocked,
        "reason": reason,
    }


def should_skip_for_spread(symbol: str) -> tuple[bool, str, dict[str, Any]]:
    status = spread_status(symbol)
    try:
        from gqos.ops.spread_regime_memory import record_spread_event
        record_spread_event(status)
    except Exception:
        pass
    return bool(status["blocked"]), str(status["reason"]), status
