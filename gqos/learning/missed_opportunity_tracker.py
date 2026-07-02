import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5
import yaml

logger = logging.getLogger("GQOS.MissedOpportunity")

PENDING_PATH = Path(os.getenv("GQOS_MISSED_PENDING_PATH", "data/learning/missed_opportunities.json"))
OUTCOMES_PATH = Path(os.getenv("GQOS_MISSED_OUTCOMES_PATH", "data/learning/missed_opportunity_outcomes.jsonl"))
MAX_PENDING = int(os.getenv("GQOS_MISSED_MAX_PENDING", "1500"))
HORIZON_MINUTES = int(os.getenv("GQOS_MISSED_HORIZON_MINUTES", "240"))
MAX_PER_EVENT = int(os.getenv("GQOS_MISSED_PROCESS_MAX_PER_EVENT", "25"))


class MissedOpportunityTracker:
    def __init__(self):
        self._evaluated_by_decision: dict[str, dict[str, Any]] = {}
        self._aliases, self._symbols = self._load_symbol_config()

    def on_event(self, event: dict[str, Any]):
        event_type = event.get("event_type")
        decision_id = str(event.get("decision_id") or "")
        if decision_id and event_type == "SIGNAL_EVALUATED":
            self._evaluated_by_decision[decision_id] = dict(event)
        if event_type in {"SIGNAL_REJECTED", "RISK_CHECK_BLOCKED"}:
            self._track(event)
        self.process_pending(limit=MAX_PER_EVENT)

    def _track(self, event: dict[str, Any]):
        if os.getenv("ENABLE_MISSED_OPPORTUNITY_TRACKER", "True").lower() not in {"1", "true", "yes"}:
            return

        decision_id = str(event.get("decision_id") or "")
        if not decision_id:
            return

        pending = self._load_pending()
        key = f"{decision_id}:{event.get('event_type')}"
        if key in pending:
            return

        meta = dict(self._evaluated_by_decision.get(decision_id, {}))
        meta.update({k: v for k, v in event.items() if v is not None})

        side = self._normalize_side(meta.get("side"))
        symbol = str(meta.get("symbol") or "")
        if not symbol or side not in {"BUY", "SELL"}:
            return

        resolved_symbol = self._resolve_symbol(symbol)
        quote = self._quote(resolved_symbol, side)
        if quote is None:
            return

        entry = quote
        sl, tp = self._build_targets(resolved_symbol, side, entry)
        if not sl or not tp or sl == tp:
            return

        row = {
            "key": key,
            "decision_id": decision_id,
            "event_type": event.get("event_type"),
            "symbol": resolved_symbol,
            "source_symbol": symbol,
            "side": side,
            "entry_time": datetime.now(timezone.utc).isoformat(),
            "entry_price": entry,
            "sl_price": sl,
            "tp_price": tp,
            "reason": event.get("reason", ""),
            "pattern_id": meta.get("pattern_id"),
            "pattern_pf": meta.get("profit_factor") or meta.get("pattern_pf"),
            "expectancy_r": meta.get("expectancy_r"),
            "pattern_similarity": meta.get("similarity") or meta.get("pattern_similarity"),
            "promotion_status": meta.get("promotion_status"),
            "status": "OPEN",
        }

        if len(pending) >= MAX_PENDING:
            oldest = sorted(pending.items(), key=lambda item: item[1].get("entry_time", ""))[: max(1, len(pending) - MAX_PENDING + 1)]
            for old_key, _ in oldest:
                pending.pop(old_key, None)
        pending[key] = row
        self._save_pending(pending)

    def process_pending(self, limit: int | None = None) -> int:
        pending = self._load_pending()
        if not pending:
            return 0

        closed = 0
        now = datetime.now(timezone.utc)
        items = sorted(pending.items(), key=lambda item: item[1].get("entry_time", ""))
        for key, row in items[: limit or len(items)]:
            result = self._evaluate(row, now)
            if not result:
                continue
            pending.pop(key, None)
            self._append_outcome(result)
            closed += 1

        if closed:
            self._save_pending(pending)
        return closed

    def _evaluate(self, row: dict[str, Any], now: datetime) -> dict[str, Any] | None:
        try:
            entry_time = datetime.fromisoformat(str(row["entry_time"]).replace("Z", "+00:00"))
        except Exception:
            entry_time = now

        symbol = row["symbol"]
        side = row["side"]
        entry = float(row["entry_price"])
        sl = float(row["sl_price"])
        tp = float(row["tp_price"])

        outcome = None
        close_price = None
        close_time = None

        rates = None
        try:
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, entry_time, now)
        except Exception:
            rates = None

        if rates is not None:
            for candle in rates:
                high = float(candle["high"])
                low = float(candle["low"])
                candle_time = datetime.fromtimestamp(int(candle["time"]), timezone.utc).isoformat()
                if side == "BUY":
                    hit_sl = low <= sl
                    hit_tp = high >= tp
                else:
                    hit_sl = high >= sl
                    hit_tp = low <= tp
                if hit_sl and hit_tp:
                    outcome, close_price = "LOSS_BOTH_HIT", sl
                elif hit_sl:
                    outcome, close_price = "LOSS", sl
                elif hit_tp:
                    outcome, close_price = "WIN", tp
                if outcome:
                    close_time = candle_time
                    break

        if not outcome and now - entry_time >= timedelta(minutes=HORIZON_MINUTES):
            close_price = self._quote(symbol, side)
            if close_price is None:
                close_price = entry
            outcome = "TIMEOUT_WIN" if self._signed_pnl(side, entry, close_price) > 0 else "TIMEOUT_LOSS"
            close_time = now.isoformat()

        if not outcome:
            return None

        sl_dist = abs(entry - sl)
        actual_r = self._signed_pnl(side, entry, close_price) / sl_dist if sl_dist > 0 else None
        return {
            **row,
            "status": "CLOSED",
            "outcome": outcome,
            "close_price": close_price,
            "close_time": close_time,
            "actual_r": round(actual_r, 4) if actual_r is not None else None,
            "missed_learning_source": "SIMULATED_REJECTED_SIGNAL",
        }

    def _build_targets(self, symbol: str, side: str, entry: float) -> tuple[float | None, float | None]:
        info = mt5.symbol_info(symbol)
        if not info:
            return None, None
        point = float(getattr(info, "point", 0.0) or 0.0)
        if point <= 0:
            return None, None

        clean = self._clean_symbol(symbol)
        cfg = self._symbols.get(clean, {})
        atr_mult = float(cfg.get("atr_sl_multiplier", 5.0))
        atr = self._recent_atr(symbol)
        buffer = atr * atr_mult if atr and atr > 0 else point * float(cfg.get("typical_spread_points", 500)) * 10.0
        buffer = max(buffer, point * 50)
        if side == "BUY":
            return entry - buffer, entry + (buffer * 2.0)
        return entry + buffer, entry - (buffer * 2.0)

    def _recent_atr(self, symbol: str) -> float | None:
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
        except Exception:
            rates = None
        if rates is None or len(rates) < 15:
            return None
        trs = []
        prev_close = None
        for candle in rates:
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
            if prev_close is None:
                tr = high - low
            else:
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
            prev_close = close
        return sum(trs[-14:]) / 14.0 if trs else None

    def _quote(self, symbol: str, side: str) -> float | None:
        if not mt5.symbol_select(symbol, True):
            return None
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None
        return float(tick.ask if side == "BUY" else tick.bid)

    def _normalize_side(self, side: Any) -> str | None:
        value = str(side or "").upper()
        if "BUY" in value or "LONG" in value:
            return "BUY"
        if "SELL" in value or "SHORT" in value:
            return "SELL"
        return None

    def _signed_pnl(self, side: str, entry: float, close: float) -> float:
        return close - entry if side == "BUY" else entry - close

    def _resolve_symbol(self, symbol: str) -> str:
        return self._aliases.get(self._clean_symbol(symbol), symbol)

    def _clean_symbol(self, symbol: str) -> str:
        value = str(symbol).upper()
        for suffix in ("M", ".M"):
            if value.endswith(suffix):
                value = value[: -len(suffix)]
        if value == "USTEC":
            return "NAS100"
        if value == "DE30":
            return "GER40"
        return value

    def _load_symbol_config(self):
        try:
            with open("config/symbols.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return cfg.get("symbol_aliases", {}), cfg.get("symbols", {})
        except Exception:
            return {}, {}

    def _load_pending(self) -> dict[str, dict[str, Any]]:
        if not PENDING_PATH.exists():
            return {}
        try:
            data = json.loads(PENDING_PATH.read_text(encoding="utf-8", errors="ignore"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_pending(self, pending: dict[str, dict[str, Any]]):
        PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
        PENDING_PATH.write_text(json.dumps(pending, indent=2), encoding="utf-8")

    def _append_outcome(self, row: dict[str, Any]):
        OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OUTCOMES_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")


missed_opportunity_tracker = MissedOpportunityTracker()
