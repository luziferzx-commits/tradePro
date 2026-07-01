"""
gqos/learning/outcome_logger.py

Trade Outcome Logger — บันทึกผลทุก trade กลับเข้า pattern database
เพื่อให้ EvidenceRouter เรียนรู้จาก live experience จริงๆ

Flow:
  Position opens  → บันทึก {ticket: pattern_id, entry_conditions}
  Position closes → ดึง pattern_id → คำนวณ actual RR → update pattern DB
"""
import logging
import json
import os
import threading
from datetime import datetime
from decimal import Decimal
from typing import Optional
import pandas as pd

logger = logging.getLogger("GQOS.OutcomeLogger")

OUTCOMES_PATH = os.getenv("GQOS_OUTCOMES_PATH", "data/learning/live_outcomes.jsonl")
PATTERN_DB_PATH = "data/pattern_store/pattern_database.parquet"
PENDING_PATH = os.getenv("GQOS_PENDING_TRADES_PATH", "data/learning/pending_trades.json")


class TradeOutcomeLogger:
    """
    บันทึก trade outcomes กลับเข้า pattern database
    ทำให้ EvidenceRouter เรียนรู้จาก live trading จริงๆ
    """

    def __init__(self, emit_structured_logs: bool = True):
        os.makedirs("data/learning", exist_ok=True)
        self._emit_structured_logs = emit_structured_logs
        self._pending: dict = self._load_pending()
        self._lock = threading.Lock()
        self._discard_stale_unlinked_intents()
        logger.info(f"OutcomeLogger initialized. Pending trades: {len(self._pending)}")

    # ──────────────────────────────────────────────
    # 1. บันทึกตอนเปิด position
    # ──────────────────────────────────────────────
    def register_intent(
        self,
        decision_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        sl_price: float,
        tp_price: float,
        pattern_id: Optional[str],
        pattern_pf: float,
        pattern_sim: float,
        session: str,
        strategy_id: str,
        source: Optional[str] = None,
        run_id: Optional[str] = None,
        account_id: Optional[str] = None,
        entry_mode: str = "NORMAL",
        probe_reason: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ):
        """เรียกเมื่อ order ถูก fill — บันทึก metadata ไว้รอ outcome"""
        
        # Calculate session based on current UTC hour if not provided
        if not session or session == "Unknown":
            hour_utc = datetime.utcnow().hour
            if 7 <= hour_utc < 10: session = "London"
            elif 13 <= hour_utc < 16: session = "NY"
            elif 16 <= hour_utc < 24: session = "Asia_Early"
            elif 0 <= hour_utc < 4: session = "Asia_Late"
            elif 4 <= hour_utc < 7: session = "Dead_PreLondon"
            else: session = "Dead_Lunch"
            
        with self._lock:
            record = {
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "pattern_id": pattern_id,
                "pattern_pf": pattern_pf,
                "pattern_similarity": pattern_sim,
                "session": session,
                "strategy_id": strategy_id,
                "decision_id": decision_id,
                "source": source or os.getenv("LEARNING_SOURCE", "LIVE"),
                "run_id": run_id or os.getenv("GQOS_RUN_ID", ""),
                "account_id": account_id or os.getenv("GQOS_ACCOUNT_ID", ""),
                "entry_mode": entry_mode,
                "probe_reason": probe_reason or "",
                "open_time": datetime.utcnow().isoformat(),
            }
            if extra_metadata:
                for key, value in extra_metadata.items():
                    if value is not None and key not in record:
                        record[key] = value
            self._pending[decision_id] = record
            self._save_pending()
            
            prefix = f"[{decision_id}] " if decision_id else ""
            logger.info(
                f"{prefix}OutcomeLogger -> Trade opened: {symbol} {direction} "
                f"pattern={pattern_id}"
            )

    # ──────────────────────────────────────────────
    # 2. บันทึกตอนปิด position
    # ──────────────────────────────────────────────
    def on_trade_opened(self, ticket: int, decision_id: str, **fields):
        with self._lock:
            meta = self._pending.pop(decision_id, None)
            if meta:
                meta['ticket'] = ticket
                for key, value in fields.items():
                    if value is not None:
                        meta[key] = value
                self._pending[str(ticket)] = meta
                self._save_pending()
                logger.info(f"[{decision_id}] Linked ticket {ticket} to pending trade.")
                try:
                    from strategy.cooldown_manager import cooldown_manager
                    cooldown_manager.record_approval(meta.get("pattern_id"))
                except Exception as exc:
                    logger.warning(f"[{decision_id}] Failed to record pattern cooldown: {exc}")
                return meta

            recovered = self._recover_pending_from_fill(ticket, decision_id, fields)
            if recovered:
                self._pending[str(ticket)] = recovered
                self._save_pending()
                logger.warning(
                    "[%s] No pending intent found; recovered ticket %s from broker fill metadata.",
                    decision_id,
                    ticket,
                )
                return recovered

            logger.warning(f"[{decision_id}] No pending intent found to link ticket {ticket}.")
            return None

    def _recover_pending_from_fill(self, ticket: int, decision_id: str, fields: dict) -> Optional[dict]:
        symbol = fields.get("symbol")
        direction = fields.get("direction")
        entry_price = (
            fields.get("fill_price")
            or fields.get("actual_entry_price")
            or fields.get("expected_entry_price")
            or fields.get("entry_price")
        )
        sl_price = fields.get("stop_loss_price") or fields.get("sl_price")

        if not symbol or not direction or entry_price is None or sl_price is None:
            return None

        try:
            entry_price = float(entry_price)
            sl_price = float(sl_price)
        except (TypeError, ValueError):
            return None
        if entry_price <= 0 or sl_price <= 0:
            return None

        record = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": fields.get("take_profit_price") or fields.get("tp_price"),
            "pattern_id": fields.get("pattern_id"),
            "pattern_pf": fields.get("pattern_pf", 0.0),
            "pattern_similarity": fields.get("pattern_similarity", 0.0),
            "session": fields.get("session") or "UNKNOWN",
            "strategy_id": fields.get("strategy_id") or "gqos_alpha_v1",
            "decision_id": decision_id,
            "source": fields.get("source") or os.getenv("LEARNING_SOURCE", "LIVE"),
            "run_id": fields.get("run_id") or os.getenv("GQOS_RUN_ID", ""),
            "account_id": fields.get("account_id") or os.getenv("GQOS_ACCOUNT_ID", ""),
            "entry_mode": fields.get("entry_mode") or "FILL_RECOVERED",
            "probe_reason": fields.get("probe_reason") or "recovered from broker fill",
            "open_time": datetime.utcnow().isoformat(),
            "ticket": ticket,
        }
        for key, value in fields.items():
            if value is not None and key not in record:
                record[key] = value
        return record

    def _discard_stale_unlinked_intents(self, max_age_minutes: int = 30):
        now = datetime.utcnow()
        removed = 0
        for key, meta in list(self._pending.items()):
            if not isinstance(meta, dict) or meta.get("ticket"):
                continue
            try:
                opened = datetime.fromisoformat(str(meta.get("open_time", "")))
            except ValueError:
                opened = now
            age_minutes = (now - opened).total_seconds() / 60.0
            if age_minutes > max_age_minutes:
                self._pending.pop(key, None)
                removed += 1
        if removed:
            self._save_pending()
            logger.info(f"[OutcomeLogger] Discarded {removed} stale unfilled intents.")

    def discard_intent_by_symbol(self, symbol: str):
        """เรียกเมื่อ signal ถูก reject จาก risk/exposure/broker เพื่อลบขยะทิ้ง"""
        with self._lock:
            keys_to_remove = []
            for key, meta in self._pending.items():
                if meta.get("symbol") == symbol and "ticket" not in meta:
                    keys_to_remove.append(key)
            
            if keys_to_remove:
                for key in keys_to_remove:
                    self._pending.pop(key, None)
                self._save_pending()
                logger.info(f"[OutcomeLogger] Discarded {len(keys_to_remove)} pending intents for {symbol} due to rejection.")

    def update_intent(self, decision_id: str, **fields):
        with self._lock:
            meta = self._pending.get(decision_id)
            if not meta:
                return False
            for key, value in fields.items():
                if value is not None:
                    meta[key] = value
            self._save_pending()
            return True

    def on_trade_closed(
        self,
        ticket: int,
        exit_price: float,
        realized_pnl: float,
        close_time: Optional[datetime] = None,
    ):
        """เรียกเมื่อ position ปิด — คำนวณ outcome แล้วบันทึก"""
        with self._lock:
            meta = self._pending.pop(str(ticket), None)
            if meta is None:
                logger.warning(
                    f"[OutcomeLogger] No pending trade for ticket={ticket}"
                )
                return None

            return self._record_closed_locked(meta, exit_price, realized_pnl, close_time)

            # คำนวณ actual R:R
            entry = meta["entry_price"]
            sl = meta["sl_price"]
            sl_dist = abs(entry - sl) if sl and sl != 0 else None

            actual_r = None
            if sl_dist and sl_dist > 0:
                actual_r = round(realized_pnl / (sl_dist * 100), 3)

            outcome = "WIN" if realized_pnl > 0 else "LOSS"

            record = {
                **meta,
                "close_price": exit_price,
                "realized_pnl": realized_pnl,
                "actual_r": actual_r,
                "outcome": outcome,
                "close_time": (close_time or datetime.utcnow()).isoformat(),
            }

            # Append to JSONL file
            with open(OUTCOMES_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            self._save_pending()

            decision_id = meta.get("decision_id", "")
            prefix = f"[{decision_id}] " if decision_id else ""
            logger.info(
                f"{prefix}OutcomeLogger -> Trade closed: {meta['symbol']} {outcome} "
                f"PnL={realized_pnl:.2f} R={actual_r} pattern={meta['pattern_id']}"
            )
            
            try:
                from gqos.common.structured_logger import log_structured_event
                if self._emit_structured_logs:
                    log_structured_event(
                        event_type="TRADE_CLOSED",
                        decision_id=decision_id,
                        symbol=meta['symbol'],
                        side=meta.get('direction', 'UNKNOWN'),
                        status=outcome,
                        reason=f"Position closed with PnL {realized_pnl:.2f}",
                        metadata={"realized_pnl": realized_pnl, "actual_r": actual_r}
                    )
            except Exception as e:
                logger.warning(f"[{decision_id}] Failed to emit structured log: {e}")

    # ──────────────────────────────────────────────
    # 3. Helper methods
    # ──────────────────────────────────────────────
    def on_trade_closed_by_symbol(
        self,
        symbol: str,
        exit_price: float,
        realized_pnl: float,
        close_time: Optional[datetime] = None,
    ):
        """Close the oldest ticket-linked pending trade for a symbol."""
        with self._lock:
            candidates = []
            for key, meta in self._pending.items():
                if meta.get("symbol") == symbol and "ticket" in meta:
                    candidates.append((key, meta))

            if not candidates:
                logger.warning(f"[OutcomeLogger] No ticket-linked pending trade for symbol={symbol}")
                return None

            candidates.sort(key=lambda item: item[1].get("open_time", ""))
            key, meta = candidates[0]
            self._pending.pop(key, None)
            return self._record_closed_locked(meta, exit_price, realized_pnl, close_time)

    def _record_closed_locked(
        self,
        meta: dict,
        exit_price: float,
        realized_pnl: float,
        close_time: Optional[datetime] = None,
    ):
        actual_r = self._calculate_actual_r(meta, realized_pnl)

        outcome = "WIN" if realized_pnl > 0 else "LOSS"

        record = {
            **meta,
            "close_price": exit_price,
            "realized_pnl": realized_pnl,
            "actual_r": actual_r,
            "outcome": outcome,
            "close_time": (close_time or datetime.utcnow()).isoformat(),
        }

        with open(OUTCOMES_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

        self._save_pending()

        decision_id = meta.get("decision_id", "")
        prefix = f"[{decision_id}] " if decision_id else ""
        logger.info(
            f"{prefix}OutcomeLogger -> Trade closed: {meta['symbol']} {outcome} "
            f"PnL={realized_pnl:.2f} R={actual_r} pattern={meta['pattern_id']}"
        )

        try:
            from gqos.common.structured_logger import log_structured_event
            if self._emit_structured_logs:
                log_structured_event(
                    event_type="TRADE_CLOSED",
                    decision_id=decision_id,
                    symbol=meta['symbol'],
                    side=meta.get('direction', 'UNKNOWN'),
                    status=outcome,
                    reason=f"Position closed with PnL {realized_pnl:.2f}",
                    metadata={
                        "realized_pnl": realized_pnl,
                        "actual_r": actual_r,
                        "source": meta.get("source", "LIVE"),
                        "run_id": meta.get("run_id", ""),
                        "account_id": meta.get("account_id", ""),
                    }
                )
        except Exception as e:
            logger.warning(f"[{decision_id}] Failed to emit structured log: {e}")

        try:
            from gqos.learning.post_trade_review import write_post_trade_review
            write_post_trade_review(record)
        except Exception as e:
            logger.warning(f"[{decision_id}] Failed to write post-trade review: {e}")

        return record

    def _first_number(self, meta: dict, *keys: str) -> Optional[float]:
        for key in keys:
            value = meta.get(key)
            if value is None or value == "":
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number == number:
                return number
        return None

    def _symbol_trade_specs(self, symbol: str) -> dict:
        try:
            import MetaTrader5 as mt5

            info = mt5.symbol_info(symbol)
            if info is None:
                return {}
            return {
                "tick_size": float(getattr(info, "trade_tick_size", 0) or getattr(info, "point", 0) or 0),
                "tick_value": float(getattr(info, "trade_tick_value", 0) or 0),
                "contract_size": float(getattr(info, "trade_contract_size", 0) or 0),
            }
        except Exception:
            return {}

    def _calculate_actual_r(self, meta: dict, realized_pnl: float) -> Optional[float]:
        entry = self._first_number(meta, "fill_price", "actual_entry_price", "entry_price")
        sl = self._first_number(meta, "stop_loss_price", "sl_price")
        volume = self._first_number(meta, "volume", "filled_volume", "quantity", "lot")

        if entry is None or sl is None or volume is None or volume <= 0:
            return None

        sl_dist = abs(entry - sl)
        if sl_dist <= 0:
            return None

        tick_size = self._first_number(meta, "tick_size", "trade_tick_size")
        tick_value = self._first_number(meta, "tick_value", "trade_tick_value")
        if not tick_size or not tick_value:
            specs = self._symbol_trade_specs(str(meta.get("symbol") or ""))
            tick_size = tick_size or specs.get("tick_size")
            tick_value = tick_value or specs.get("tick_value")

        if not tick_size or not tick_value or tick_size <= 0 or tick_value <= 0:
            logger.warning(
                "[OutcomeLogger] Cannot calculate actual R for ticket=%s symbol=%s: "
                "missing tick_size/tick_value/volume metadata",
                meta.get("ticket"),
                meta.get("symbol"),
            )
            return None

        risk_amount = (sl_dist / tick_size) * tick_value * volume
        if risk_amount <= 0:
            return None
        return round(float(realized_pnl) / risk_amount, 3)

    def get_outcomes_df(self, allowed_sources: Optional[set[str] | list[str] | tuple[str, ...]] = None) -> pd.DataFrame:
        """โหลด live outcomes ทั้งหมด"""
        if not os.path.exists(OUTCOMES_PATH):
            return pd.DataFrame()
        records = []
        with open(OUTCOMES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        df = pd.DataFrame(records)
        if df.empty:
            return df

        if "source" not in df.columns:
            df["source"] = "LIVE"

        if allowed_sources:
            allowed = {str(s).strip().upper() for s in allowed_sources}
            df = df[df["source"].fillna("LIVE").astype(str).str.upper().isin(allowed)]

        return df

    def get_stats(self) -> dict:
        """สรุปสถิติ live trading"""
        df = self.get_outcomes_df()
        if df.empty:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "total_pnl": 0.0}
        wins = len(df[df["outcome"] == "WIN"])
        total = len(df)
        return {
            "total": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1),
            "total_pnl": round(df["realized_pnl"].sum(), 2),
            "avg_r": round(df["actual_r"].dropna().mean(), 3),
        }

    def reload_pending(self) -> int:
        """Reload pending metadata after an external MT5 sync restores tickets."""
        with self._lock:
            self._pending = self._load_pending()
            return len(self._pending)

    def _load_pending(self) -> dict:
        if os.path.exists(PENDING_PATH):
            try:
                with open(PENDING_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_pending(self):
        with open(PENDING_PATH, "w") as f:
            json.dump(self._pending, f, indent=2)


# Singleton
outcome_logger = TradeOutcomeLogger()
