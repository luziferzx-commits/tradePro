import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market.session_detector import SessionDetector


EVENTS_PATH = Path(os.getenv("GQOS_SPREAD_REGIME_EVENTS_PATH", "data/learning/spread_regime_events.jsonl"))


def _market_session(symbol: str) -> str:
    hour = datetime.now(timezone.utc).hour
    clean = str(symbol or "").upper().replace("M", "")
    if clean in {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"}:
        if 0 <= hour < 7:
            return "CRYPTO_ASIA"
        if 7 <= hour < 13:
            return "CRYPTO_EU"
        if 13 <= hour < 21:
            return "CRYPTO_US"
        return "CRYPTO_ROLLOVER"
    if clean in {"NAS100", "US500", "US30", "USTEC"}:
        if 13 <= hour < 14:
            return "US_PRE_CASH"
        if 14 <= hour < 20:
            return "US_CASH"
        if 20 <= hour < 22:
            return "US_LATE"
        return "US_OFF_HOURS"
    return SessionDetector.detect(datetime.now(timezone.utc).timestamp())


def record_spread_event(status: dict[str, Any]) -> None:
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": status.get("symbol"),
        "broker": status.get("broker"),
        "spread": status.get("spread"),
        "max_spread": status.get("max_spread"),
        "spread_ratio": status.get("ratio"),
        "blocked": bool(status.get("blocked")),
        "reason": status.get("reason", ""),
        "session": SessionDetector.detect(datetime.now(timezone.utc).timestamp()),
        "market_session": _market_session(str(status.get("symbol") or "")),
    }
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _read_events(limit: int = 5000) -> list[dict[str, Any]]:
    if not EVENTS_PATH.exists():
        return []
    rows = []
    with EVENTS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
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


def spread_regime_summary(min_samples: int = 5) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _read_events():
        grouped[(str(row.get("symbol")), str(row.get("market_session") or row.get("session")))].append(row)
    summary = []
    for (symbol, session), rows in grouped.items():
        if len(rows) < min_samples:
            continue
        blocked = sum(1 for row in rows if row.get("blocked"))
        avg_ratio_vals = [float(row.get("spread_ratio") or 0.0) for row in rows if row.get("spread_ratio") is not None]
        avg_ratio = sum(avg_ratio_vals) / len(avg_ratio_vals) if avg_ratio_vals else 0.0
        block_rate = blocked / len(rows)
        reliable = len(rows) >= 5
        summary.append({
            "symbol": symbol,
            "session": session,
            "samples": len(rows),
            "blocked": blocked,
            "block_rate": block_rate,
            "avg_spread_ratio": avg_ratio,
            "label": "COLLECTING" if not reliable else (
                "DO_NOT_TRADE" if block_rate >= 0.65 else ("WATCH_SPREAD" if block_rate >= 0.35 else "OK")
            ),
        })
    return sorted(summary, key=lambda row: (row["block_rate"], row["samples"]), reverse=True)


def is_do_not_trade_window(symbol: str) -> tuple[bool, str]:
    if os.getenv("ENABLE_DO_NOT_TRADE_WINDOW", "True").lower() not in {"1", "true", "yes"}:
        return False, ""
    current = _market_session(symbol)
    clean = str(symbol or "").upper()
    for row in spread_regime_summary():
        if str(row["symbol"]).upper() == clean and row["session"] == current and row["label"] == "DO_NOT_TRADE":
            return True, f"Do-not-trade spread regime: {clean} {current} block_rate={row['block_rate']:.0%}"
    return False, ""


def build_spread_regime_report(limit: int = 10) -> str:
    rows = spread_regime_summary(min_samples=1)[:limit]
    if not rows:
        return "Spread Regime Memory\nNo spread regime history yet."
    lines = ["Spread Regime Memory"]
    for row in rows:
        lines.append(
            f"- {row['symbol']} {row['session']}: {row['label']} "
            f"block={row['block_rate']:.0%} avgRatio={row['avg_spread_ratio']:.1f} N={row['samples']}"
        )
    return "\n".join(lines)
