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

OUTCOMES_PATH = "data/learning/live_outcomes.jsonl"
PATTERN_DB_PATH = "data/pattern_store/pattern_database.parquet"
PENDING_PATH = "data/learning/pending_trades.json"


class TradeOutcomeLogger:
    """
    บันทึก trade outcomes กลับเข้า pattern database
    ทำให้ EvidenceRouter เรียนรู้จาก live trading จริงๆ
    """

    def __init__(self):
        os.makedirs("data/learning", exist_ok=True)
        self._pending: dict = self._load_pending()
        self._lock = threading.Lock()
        logger.info(f"OutcomeLogger initialized. Pending trades: {len(self._pending)}")

    # ──────────────────────────────────────────────
    # 1. บันทึกตอนเปิด position
    # ──────────────────────────────────────────────
    def on_trade_opened(
        self,
        ticket: str,
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
    ):
        """เรียกเมื่อ order ถูก fill — บันทึก metadata ไว้รอ outcome"""
        with self._lock:
            self._pending[ticket] = {
                "ticket": ticket,
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
                "open_time": datetime.utcnow().isoformat(),
            }
            self._save_pending()
            logger.info(
                f"[OutcomeLogger] Trade opened: {symbol} {direction} "
                f"ticket={ticket} pattern={pattern_id}"
            )

    # ──────────────────────────────────────────────
    # 2. บันทึกตอนปิด position
    # ──────────────────────────────────────────────
    def on_trade_closed(
        self,
        ticket: str,
        close_price: float,
        realized_pnl: float,
        close_time: Optional[datetime] = None,
    ):
        """เรียกเมื่อ position ปิด — คำนวณ outcome แล้วบันทึก"""
        with self._lock:
            meta = self._pending.pop(ticket, None)
            if meta is None:
                logger.warning(
                    f"[OutcomeLogger] No pending trade for ticket={ticket}"
                )
                return

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
                "close_price": close_price,
                "realized_pnl": realized_pnl,
                "actual_r": actual_r,
                "outcome": outcome,
                "close_time": (close_time or datetime.utcnow()).isoformat(),
            }

            # Append to JSONL file
            with open(OUTCOMES_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            self._save_pending()

            logger.info(
                f"[OutcomeLogger] Trade closed: {meta['symbol']} {outcome} "
                f"PnL={realized_pnl:.2f} R={actual_r} pattern={meta['pattern_id']}"
            )

    # ──────────────────────────────────────────────
    # 3. Helper methods
    # ──────────────────────────────────────────────
    def get_outcomes_df(self) -> pd.DataFrame:
        """โหลด live outcomes ทั้งหมด"""
        if not os.path.exists(OUTCOMES_PATH):
            return pd.DataFrame()
        records = []
        with open(OUTCOMES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return pd.DataFrame(records)

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
