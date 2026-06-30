import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from config.settings import settings
from execution.mt5_direction import closing_deal_position_direction

logger = logging.getLogger("GQOS.MT5OutcomeSync")

OUTCOMES_PATH = Path(os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl"))
PENDING_PATH = Path(os.getenv("GQOS_PENDING_TRADES_PATH", "data/learning/pending_trades.json"))
SYSTEM_EVENTS_PATH = Path(os.getenv("GQOS_SYSTEM_EVENTS_FILE", "data/learning/system_events.jsonl"))


def _existing_keys() -> set[str]:
    keys: set[str] = set()
    if not OUTCOMES_PATH.exists():
        return keys
    with OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key_name in ("deal_ticket", "ticket"):
                value = item.get(key_name)
                if value is not None and str(value):
                    keys.add(f"{key_name}:{value}")
    return keys


def _metadata_from_record(record: dict) -> dict:
    direction = record.get("direction") or record.get("side")
    if isinstance(direction, str):
        direction = {"LONG": "BUY", "SHORT": "SELL"}.get(direction.upper(), direction)
    return {
        "ticket": record.get("ticket") or record.get("order") or record.get("position_id"),
        "deal_ticket": record.get("deal_ticket"),
        "symbol": record.get("symbol"),
        "direction": direction,
        "entry_price": record.get("entry_price"),
        "sl_price": record.get("sl_price") or record.get("stop_loss_price"),
        "tp_price": record.get("tp_price") or record.get("take_profit_price"),
        "pattern_id": record.get("pattern_id"),
        "pattern_pf": record.get("pattern_pf") or record.get("profit_factor") or record.get("historical_pf"),
        "pattern_similarity": record.get("pattern_similarity") or record.get("similarity") or record.get("similarity_score"),
        "session": record.get("session") or record.get("session_label") or record.get("promotion_status"),
        "strategy_id": record.get("strategy_id") or "gqos_alpha_v1",
        "decision_id": record.get("decision_id"),
        "source": record.get("source") or "LIVE",
        "run_id": record.get("run_id") or os.getenv("GQOS_RUN_ID", ""),
        "account_id": record.get("account_id") or str(settings.MT5_LOGIN or ""),
        "entry_mode": record.get("entry_mode") or "NORMAL",
        "probe_reason": record.get("probe_reason") or "",
        "open_time": record.get("open_time"),
    }


def _merge_meta(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _load_metadata_index() -> dict:
    by_ticket: dict[str, dict] = {}
    by_decision: dict[str, dict] = {}
    by_comment_suffix: dict[str, dict] = {}

    def remember(meta: dict):
        if not meta:
            return
        meta = _metadata_from_record(meta)
        decision_id = str(meta.get("decision_id") or "")
        if decision_id:
            by_decision[decision_id] = _merge_meta(by_decision.get(decision_id, {}), meta)
            suffix = decision_id.split("-")[-1]
            if suffix:
                by_comment_suffix[suffix.upper()] = by_decision[decision_id]
        ticket = meta.get("ticket")
        if ticket:
            by_ticket[str(ticket)] = _merge_meta(by_ticket.get(str(ticket), {}), meta)

    if PENDING_PATH.exists():
        try:
            pending = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
            if isinstance(pending, dict):
                for key, meta in pending.items():
                    if isinstance(meta, dict):
                        row = dict(meta)
                        row.setdefault("decision_id", key if str(key).startswith("GQOS-") else meta.get("decision_id"))
                        remember(row)
                        if str(key).isdigit():
                            by_ticket[str(key)] = _merge_meta(by_ticket.get(str(key), {}), _metadata_from_record(row))
        except Exception as exc:
            logger.debug("[MT5OutcomeSync] Could not read pending metadata: %s", exc)

    if OUTCOMES_PATH.exists():
        with OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                remember(row)

    if SYSTEM_EVENTS_PATH.exists():
        signal_meta_by_decision: dict[str, dict] = {}
        ticket_to_decision: dict[str, str] = {}
        with SYSTEM_EVENTS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                decision_id = str(event.get("decision_id") or "")
                event_type = event.get("event_type")
                if decision_id and event_type in {"SIGNAL_EVALUATED", "SIGNAL_REJECTED"}:
                    signal_meta_by_decision[decision_id] = _merge_meta(
                        signal_meta_by_decision.get(decision_id, {}),
                        _metadata_from_record(event),
                    )
                ticket = (event.get("ticket") or (event.get("metadata") or {}).get("ticket"))
                if decision_id and ticket:
                    ticket_to_decision[str(ticket)] = decision_id

        for decision_id, meta in signal_meta_by_decision.items():
            by_decision[decision_id] = _merge_meta(by_decision.get(decision_id, {}), meta)
            suffix = decision_id.split("-")[-1]
            if suffix:
                by_comment_suffix[suffix.upper()] = by_decision[decision_id]
        for ticket, decision_id in ticket_to_decision.items():
            by_ticket[ticket] = _merge_meta(by_ticket.get(ticket, {}), by_decision.get(decision_id, {"decision_id": decision_id}))

    return {
        "by_ticket": by_ticket,
        "by_decision": by_decision,
        "by_comment_suffix": by_comment_suffix,
    }


def _metadata_for_deal(deal, index: dict) -> dict:
    position_id = str(getattr(deal, "position_id", "") or "")
    order_id = str(getattr(deal, "order", "") or "")
    by_ticket = index.get("by_ticket", {})
    for key in (position_id, order_id):
        if key and key in by_ticket:
            return by_ticket[key]

    try:
        orders = mt5.history_orders_get(position=getattr(deal, "position_id", 0)) or []
    except Exception:
        orders = []
    by_comment_suffix = index.get("by_comment_suffix", {})
    for order in orders:
        comment = str(getattr(order, "comment", "") or "").upper()
        for suffix, meta in by_comment_suffix.items():
            if suffix and suffix in comment:
                return meta
    return {}


def _metadata_for_position_ticket(ticket: str, index: dict) -> dict:
    by_ticket = index.get("by_ticket", {})
    if ticket and ticket in by_ticket:
        return by_ticket[ticket]

    try:
        orders = mt5.history_orders_get(position=int(ticket)) or []
    except Exception:
        orders = []

    by_comment_suffix = index.get("by_comment_suffix", {})
    for order in orders:
        order_ticket = str(getattr(order, "ticket", "") or "")
        if order_ticket and order_ticket in by_ticket:
            return by_ticket[order_ticket]
        comment = str(getattr(order, "comment", "") or "").upper()
        for suffix, meta in by_comment_suffix.items():
            if suffix and suffix in comment:
                return meta
    return {}


def _day_bounds() -> tuple[datetime, datetime]:
    guard_tz = ZoneInfo(getattr(settings, "DAILY_GUARD_TIMEZONE", "Asia/Bangkok"))
    now_local = datetime.now(guard_tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        now_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def sync_mt5_closed_deals_today() -> int:
    start_utc, end_utc = _day_bounds()
    deals = mt5.history_deals_get(start_utc, end_utc) or []
    existing = _existing_keys()
    metadata_index = _load_metadata_index()
    rows = []

    for deal in deals:
        if getattr(deal, "entry", None) != mt5.DEAL_ENTRY_OUT:
            continue
        profit = float(getattr(deal, "profit", 0.0))
        if profit == 0.0:
            continue

        deal_ticket = str(getattr(deal, "ticket", ""))
        position_id = str(getattr(deal, "position_id", "") or deal_ticket)
        if f"deal_ticket:{deal_ticket}" in existing or f"ticket:{position_id}" in existing:
            continue
        meta = _metadata_for_deal(deal, metadata_index)

        rows.append(
            {
                "symbol": deal.symbol,
                "direction": meta.get("direction") or closing_deal_position_direction(deal.type),
                "entry_price": meta.get("entry_price"),
                "sl_price": meta.get("sl_price"),
                "tp_price": meta.get("tp_price"),
                "pattern_id": meta.get("pattern_id"),
                "pattern_pf": meta.get("pattern_pf"),
                "pattern_similarity": meta.get("pattern_similarity"),
                "session": meta.get("session") or "MT5_HISTORY",
                "strategy_id": meta.get("strategy_id") or "mt5_history",
                "decision_id": meta.get("decision_id") or f"MT5-{position_id}",
                "source": meta.get("source") or "LIVE",
                "run_id": meta.get("run_id") or os.getenv("GQOS_RUN_ID", ""),
                "account_id": meta.get("account_id") or str(settings.MT5_LOGIN or ""),
                "entry_mode": meta.get("entry_mode") or "NORMAL",
                "probe_reason": meta.get("probe_reason") or "",
                "open_time": meta.get("open_time"),
                "ticket": position_id,
                "deal_ticket": deal_ticket,
                "close_price": float(getattr(deal, "price", 0.0)),
                "realized_pnl": profit,
                "actual_r": None,
                "outcome": "WIN" if profit > 0 else "LOSS",
                "close_time": datetime.utcfromtimestamp(deal.time).isoformat(),
                "sync_source": "mt5_history_backfill",
            }
        )

    if not rows:
        return 0

    OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTCOMES_PATH.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    logger.info("[MT5OutcomeSync] Backfilled %s closed deals into %s", len(rows), OUTCOMES_PATH)
    return len(rows)


def sync_mt5_open_positions_to_pending() -> int:
    """Restore pending-learning metadata for live positions after bot restarts."""
    index = _load_metadata_index()
    by_comment_suffix = index.get("by_comment_suffix", {})
    if not by_comment_suffix:
        return 0

    try:
        pending = json.loads(PENDING_PATH.read_text(encoding="utf-8")) if PENDING_PATH.exists() else {}
    except Exception:
        pending = {}
    if not isinstance(pending, dict):
        pending = {}

    changed = 0
    positions = mt5.positions_get() or []
    for position in positions:
        ticket = str(getattr(position, "ticket", "") or "")
        if not ticket or ticket in pending:
            continue

        comment = str(getattr(position, "comment", "") or "").upper()
        meta = {}
        for suffix, candidate in by_comment_suffix.items():
            if suffix and suffix in comment:
                meta = candidate
                break
        if not meta or not meta.get("pattern_id"):
            continue

        direction = "SELL" if getattr(position, "type", None) == mt5.POSITION_TYPE_SELL else "BUY"
        row = _merge_meta(
            meta,
            {
                "ticket": ticket,
                "symbol": getattr(position, "symbol", None),
                "direction": direction,
                "entry_price": float(getattr(position, "price_open", 0.0) or 0.0),
                "sl_price": float(getattr(position, "sl", 0.0) or 0.0),
                "tp_price": float(getattr(position, "tp", 0.0) or 0.0),
                "source": meta.get("source") or "LIVE",
                "open_time": meta.get("open_time") or datetime.utcnow().isoformat(),
            },
        )
        pending[ticket] = row
        changed += 1

    if changed:
        PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
        PENDING_PATH.write_text(json.dumps(pending, indent=2), encoding="utf-8")
        logger.info("[MT5OutcomeSync] Restored %s open positions into pending outcomes", changed)
    return changed


def enrich_existing_outcomes() -> int:
    if not OUTCOMES_PATH.exists():
        return 0
    index = _load_metadata_index()
    changed = 0
    rows = []
    with OUTCOMES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rows.append(None)
                continue
            if not row.get("pattern_id"):
                meta = {}
                ticket = str(row.get("ticket") or "")
                if ticket:
                    meta = _metadata_for_position_ticket(ticket, index)
                if not meta and row.get("decision_id"):
                    meta = index.get("by_decision", {}).get(str(row.get("decision_id")), {})
                if meta and meta.get("pattern_id"):
                    for key in (
                        "pattern_id",
                        "pattern_pf",
                        "pattern_similarity",
                        "session",
                        "strategy_id",
                        "decision_id",
                        "source",
                        "run_id",
                        "account_id",
                        "entry_mode",
                        "probe_reason",
                        "open_time",
                        "entry_price",
                        "sl_price",
                        "tp_price",
                    ):
                        if meta.get(key) is not None and meta.get(key) != "":
                            row[key] = meta[key]
                    row["sync_enriched"] = True
                    changed += 1
            rows.append(row)

    if changed:
        with OUTCOMES_PATH.open("w", encoding="utf-8") as f:
            for row in rows:
                if row is not None:
                    f.write(json.dumps(row) + "\n")
    return changed
