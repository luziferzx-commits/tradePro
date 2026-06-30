import html
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5
import yaml

from config.settings import settings

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_EVENTS_PATH = PROJECT_ROOT / "data" / "learning" / "system_events.jsonl"
SYMBOLS_PATH = PROJECT_ROOT / "config" / "symbols.yaml"


def _load_symbol_config() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    try:
        with SYMBOLS_PATH.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("symbols", {}) or {}, cfg.get("symbol_aliases", {}) or {}
    except Exception as exc:
        logger.warning("Could not load symbols.yaml: %s", exc)
        return {}, {}


def _today_bounds() -> tuple[datetime, datetime]:
    try:
        guard_tz = ZoneInfo(settings.DAILY_GUARD_TIMEZONE)
    except Exception:
        guard_tz = ZoneInfo("Asia/Bangkok")
    now_local = datetime.now(guard_tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = now_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def get_today_closed_deals() -> list[Any]:
    start, end = _today_bounds()
    deals = mt5.history_deals_get(start, end)
    if not deals:
        return []
    return [
        d
        for d in deals
        if getattr(d, "entry", None) == mt5.DEAL_ENTRY_OUT
        and _safe_float(getattr(d, "profit", 0.0)) != 0.0
    ]


def get_daily_pnl() -> tuple[float, int, int, int]:
    deals = get_today_closed_deals()
    pnl = sum(_safe_float(getattr(d, "profit", 0.0)) for d in deals)
    wins = sum(1 for d in deals if _safe_float(getattr(d, "profit", 0.0)) > 0)
    losses = sum(1 for d in deals if _safe_float(getattr(d, "profit", 0.0)) < 0)
    return pnl, len(deals), wins, losses


def get_entry_block_reason(balance: float) -> str | None:
    daily_pnl, trades, _, losses = get_daily_pnl()
    if (
        settings.ENABLE_AUTO_PAUSE_BAD_START
        and trades >= settings.AUTO_PAUSE_BAD_START_TRADES
        and losses >= settings.AUTO_PAUSE_BAD_START_LOSSES
    ):
        return (
            f"Bad-start guard active: {losses} losses from "
            f"{trades} closed trades today."
        )
    if balance > 0 and daily_pnl <= -balance * settings.MAX_DAILY_LOSS_PCT:
        return (
            f"Daily-loss guard active: daily PnL {daily_pnl:+.2f} "
            f"<= {-balance * settings.MAX_DAILY_LOSS_PCT:.2f}."
        )
    if (
        settings.ENABLE_DAILY_PROFIT_LOCK
        and balance > 0
        and daily_pnl >= balance * settings.DAILY_PROFIT_LOCK_PCT
    ):
        return (
            f"Daily profit lock active: daily PnL {daily_pnl:+.2f} "
            f">= {balance * settings.DAILY_PROFIT_LOCK_PCT:.2f}."
        )
    return None


def _entry_guard_action_text() -> str:
    if settings.LIVE_GUARD_ENTRY_ACTION == "PROBE":
        return (
            f"New entries will run as guarded probes at "
            f"{settings.LIVE_GUARD_PROBE_MULTIPLIER:.2f}x size."
        )
    return "Restart will manage existing positions but should pause new entries."


def get_enabled_symbols() -> list[dict[str, Any]]:
    symbols, aliases = _load_symbol_config()
    rows = []
    for logical, cfg in symbols.items():
        if not isinstance(cfg, dict) or not cfg.get("enabled", False):
            continue
        rows.append(
            {
                "logical": logical,
                "broker": aliases.get(logical, logical),
                "max_spread_points": cfg.get("max_spread_points"),
                "min_profit_factor": cfg.get("min_profit_factor"),
            }
        )
    return rows


def read_recent_signal_events(limit: int = 500) -> list[dict[str, Any]]:
    if not SYSTEM_EVENTS_PATH.exists():
        return []
    try:
        lines = SYSTEM_EVENTS_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception as exc:
        logger.warning("Could not read system events: %s", exc)
        return []

    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if item.get("event_type") in {
            "SIGNAL_EVALUATED",
            "SIGNAL_REJECTED",
            "RISK_CHECK_BLOCKED",
            "ORDER_REJECTED",
            "ORDER_FILLED",
        }:
            events.append(item)
    return events


def latest_event_by_symbol(limit: int = 500) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in read_recent_signal_events(limit=limit):
        symbol = str(event.get("symbol", "")).replace("m", "")
        if symbol:
            latest[symbol] = event
    return latest


def build_symbol_scoreboard(max_rows: int = 25) -> str:
    enabled = get_enabled_symbols()
    latest = latest_event_by_symbol()
    positions = mt5.positions_get() or []
    open_symbols = {str(p.symbol).replace("m", "") for p in positions}

    rows = []
    try:
        from gqos.risk.portfolio_budget import portfolio_budget
    except Exception:
        portfolio_budget = None

    for item in enabled:
        logical = item["logical"]
        broker = item["broker"]
        info = mt5.symbol_info(broker)
        event = latest.get(logical, {})
        reason = event.get("reason", "No recent signal")
        status = event.get("status", "WAIT")
        spread = getattr(info, "spread", None) if info else None
        max_spread = item.get("max_spread_points")
        spread_ok = info is not None and (
            max_spread is None or _safe_float(spread, 999999.0) <= _safe_float(max_spread)
        )
        budget = None
        if portfolio_budget is not None:
            try:
                budget = portfolio_budget.get_multiplier(broker)
            except Exception:
                budget = None
        rows.append(
            {
                "symbol": logical,
                "status": "OPEN" if logical in open_symbols else status,
                "spread": spread,
                "spread_ok": spread_ok,
                "budget": budget,
                "pf": event.get("profit_factor"),
                "expr": event.get("expectancy_r"),
                "reason": reason,
            }
        )

    rows.sort(key=lambda r: (r["status"] != "OPEN", r["symbol"]))
    lines = ["<b>GQOS Symbol Scoreboard</b>"]
    for row in rows[:max_rows]:
        spread_text = "NA" if row["spread"] is None else str(row["spread"])
        budget_text = "NA" if row["budget"] is None else f"{row['budget']:.2f}x"
        pf_text = "NA" if row["pf"] is None else f"{_safe_float(row['pf']):.2f}"
        exp_text = "NA" if row["expr"] is None else f"{_safe_float(row['expr']):.2f}"
        spread_flag = "OK" if row["spread_ok"] else "WIDE"
        reason = html.escape(str(row["reason"]))[:90]
        lines.append(
            f"{row['symbol']}: {row['status']} | spr {spread_text} {spread_flag} | "
            f"budget {budget_text} | PF {pf_text} | ExpR {exp_text} | {reason}"
        )
    return "\n".join(lines)


def build_startup_summary() -> str:
    acc = mt5.account_info()
    positions = mt5.positions_get() or []
    enabled = get_enabled_symbols()
    daily_pnl, trades, wins, losses = get_daily_pnl()
    state = "LIVE" if settings.ALLOW_LIVE_TRADING and not settings.DRY_RUN else "DRY/SAFE"

    lines = ["<b>GQOS Live Engine Started</b>"]
    lines.append(f"Mode: {state} | micro={settings.LIVE_MICRO_MODE}")
    if acc:
        lines.append(
            f"Balance: {acc.balance:.2f} | Equity: {acc.equity:.2f} | Float: {acc.profit:.2f}"
        )
    lines.append(f"Open positions: {len(positions)}/{settings.MAX_OPEN_POSITIONS}")
    lines.append(
        f"Risk: {settings.MAX_REAL_RISK_PER_TRADE_PCT*100:.2f}%/trade | "
        f"throttle {settings.TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR}/h global, "
        f"{settings.TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR}/h symbol"
    )
    lines.append(
        f"Symbols enabled: {len(enabled)} | corr cap {settings.MAX_CORRELATED_POSITIONS_PER_GROUP}"
    )
    lines.append(
        f"Today: {daily_pnl:+.2f} USD | trades {trades} ({wins}W/{losses}L)"
    )
    lines.append(
        f"Recovery probe: {settings.ENABLE_PAUSED_SYMBOL_RECOVERY_PROBE} | "
        f"profit lock {settings.DAILY_PROFIT_LOCK_PCT*100:.2f}% | "
        f"daily loss stop {settings.MAX_DAILY_LOSS_PCT*100:.2f}%"
    )
    return "\n".join(lines)


def build_health_report() -> tuple[bool, str]:
    ok = True
    lines = ["GQOS Pre-Restart Health Check"]

    acc = mt5.account_info()
    if not acc:
        return False, "\n".join(lines + ["FAIL MT5 account_info unavailable"])

    lines.append(f"PASS MT5 connected: login={acc.login}, server={acc.server}")
    lines.append(f"Account: balance={acc.balance:.2f}, equity={acc.equity:.2f}, float={acc.profit:.2f}")
    lines.append(
        f"Config: live={settings.ALLOW_LIVE_TRADING}, dry_run={settings.DRY_RUN}, "
        f"micro={settings.LIVE_MICRO_MODE}, max_positions={settings.MAX_OPEN_POSITIONS}, "
        f"risk_cap={settings.MAX_REAL_RISK_PER_TRADE_PCT*100:.2f}%"
    )
    lines.append(
        f"Throttle: global/h={settings.TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR}, "
        f"symbol/h={settings.TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR}, "
        f"corr_cap={settings.MAX_CORRELATED_POSITIONS_PER_GROUP}"
    )

    positions = mt5.positions_get() or []
    lines.append(f"Open positions: {len(positions)}")
    for p in positions[:12]:
        side = "BUY" if getattr(p, "type", 0) == mt5.POSITION_TYPE_BUY else "SELL"
        lines.append(f"  {p.symbol} {side} lot={p.volume} pnl={p.profit:.2f}")

    enabled = get_enabled_symbols()
    missing = []
    wide = []
    for item in enabled:
        info = mt5.symbol_info(item["broker"])
        if info is None:
            missing.append(item["logical"])
            ok = False
            continue
        max_spread = item.get("max_spread_points")
        if max_spread is not None and _safe_float(info.spread) > _safe_float(max_spread):
            wide.append(f"{item['logical']} spr={info.spread}>{max_spread}")

    lines.append(f"Enabled symbols: {len(enabled)}")
    if missing:
        lines.append("FAIL missing broker symbols: " + ", ".join(missing))
    else:
        lines.append("PASS all enabled symbols found at broker")

    if wide:
        lines.append("WARN wide spreads now: " + "; ".join(wide[:10]))
        if len(wide) > 10:
            lines.append(f"WARN wide spread list truncated: +{len(wide)-10} more")
    else:
        lines.append("PASS all enabled symbol spreads are inside configured max")

    daily_pnl, trades, wins, losses = get_daily_pnl()
    lines.append(f"Today closed PnL: {daily_pnl:+.2f} USD from {trades} trades ({wins}W/{losses}L)")
    if (
        settings.ENABLE_AUTO_PAUSE_BAD_START
        and trades >= settings.AUTO_PAUSE_BAD_START_TRADES
        and losses >= settings.AUTO_PAUSE_BAD_START_LOSSES
    ):
        ok = False
        lines.append(
            f"FAIL bad-start guard: {losses} losses from {trades} trades today. "
            f"{_entry_guard_action_text()}"
        )
    daily_loss_limit = -float(acc.balance) * settings.MAX_DAILY_LOSS_PCT
    if daily_pnl <= daily_loss_limit:
        ok = False
        lines.append(
            f"FAIL daily loss guard: {daily_pnl:+.2f} <= {daily_loss_limit:.2f}. "
            f"{_entry_guard_action_text()}"
        )
    lines.append("Decision: " + ("PASS restart is allowed" if ok else "FAIL fix blocking items first"))
    return ok, "\n".join(lines)


@dataclass
class LiveSessionGuard:
    alpha_worker: Any
    circuit_breaker: Any
    started_at: datetime = field(default_factory=datetime.utcnow)
    closed_pnls: list[float] = field(default_factory=list)
    profit_locked: bool = False
    bad_start_paused: bool = False

    def enforce_startup_limits(self, balance: float) -> str | None:
        reason = get_entry_block_reason(balance)
        if reason:
            return self._apply_entry_guard(reason, startup=True)
        return None

    def _apply_entry_guard(self, reason: str, startup: bool = False) -> str:
        prefix = "Startup guard" if startup else "Live guard"
        if settings.LIVE_GUARD_ENTRY_ACTION == "PROBE":
            self.alpha_worker.is_paused = False
            self.alpha_worker.guard_probe_reason = reason
            message = (
                f"{prefix} enabled guarded probe mode: {reason} "
                f"New entries are limited to {settings.LIVE_GUARD_PROBE_MULTIPLIER:.2f}x size."
            )
        else:
            self.alpha_worker.is_paused = True
            self.alpha_worker.guard_probe_reason = ""
            message = f"{prefix} paused new entries: {reason}"

            if reason.startswith("Bad-start"):
                self.bad_start_paused = True
                self._trip("BAD_START_GUARD", reason)
            elif reason.startswith("Daily-loss"):
                self._trip("DAILY_LOSS_LIMIT", reason)
            elif reason.startswith("Daily profit"):
                self.profit_locked = True
        return message

    def record_closed_trade(self, symbol: str, pnl: float, balance: float, equity: float | None = None) -> str | None:
        self.closed_pnls.append(float(pnl))

        if self._should_pause_bad_start(balance=balance, equity=equity):
            self.bad_start_paused = True
            reason = (
                f"Bad-start guard active after {len(self.closed_pnls)} closed trades: "
                f"{sum(1 for x in self.closed_pnls[:settings.AUTO_PAUSE_BAD_START_TRADES] if x < 0)} losses."
            )
            self._trip("BAD_START_GUARD", reason)
            return self._apply_entry_guard(reason)

        daily_pnl, _, _, _ = get_daily_pnl()
        if self._should_profit_lock(daily_pnl=daily_pnl, balance=balance):
            self.profit_locked = True
            reason = (
                f"Daily profit lock active: daily PnL {daily_pnl:+.2f} "
                f">= {balance * settings.DAILY_PROFIT_LOCK_PCT:.2f}."
            )
            return self._apply_entry_guard(reason)

        return None

    def _should_pause_bad_start(self, balance: float, equity: float | None) -> bool:
        if not settings.ENABLE_AUTO_PAUSE_BAD_START or self.bad_start_paused:
            return False
        n = settings.AUTO_PAUSE_BAD_START_TRADES
        if len(self.closed_pnls) >= n:
            first = self.closed_pnls[:n]
            losses = sum(1 for x in first if x < 0)
            if losses >= settings.AUTO_PAUSE_BAD_START_LOSSES:
                return True
        if equity is not None and balance > 0:
            floating_dd = max(0.0, (balance - equity) / balance)
            if floating_dd >= settings.AUTO_PAUSE_FLOATING_DD_PCT:
                return True
        return False

    def _should_profit_lock(self, daily_pnl: float, balance: float) -> bool:
        return (
            settings.ENABLE_DAILY_PROFIT_LOCK
            and not self.profit_locked
            and balance > 0
            and daily_pnl >= balance * settings.DAILY_PROFIT_LOCK_PCT
        )

    def _trip(self, breaker_id: str, reason: str) -> None:
        try:
            self.circuit_breaker.trip(breaker_id, reason)
        except Exception as exc:
            logger.warning("Could not trip circuit breaker %s: %s", breaker_id, exc)


def summarize_rejection_reasons(limit: int = 500) -> str:
    events = read_recent_signal_events(limit=limit)
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        if event.get("status") in {"REJECTED", "BLOCKED"}:
            counts[str(event.get("reason", "Unknown"))] += 1
    if not counts:
        return "No recent rejections recorded."
    lines = ["Recent rejection reasons:"]
    for reason, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]:
        lines.append(f"{count}x {reason}")
    return "\n".join(lines)
