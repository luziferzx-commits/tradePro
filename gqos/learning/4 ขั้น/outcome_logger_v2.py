"""
gqos/learning/outcome_logger.py  (v2 — ใช้ symbol เป็น key)

แก้ให้ตรงกับ event structure จริง:
- RealizedPnLEmittedEvent: strategy_id, symbol, realized_pnl
- PositionClosedEvent: strategy_id, symbol, direction, quantity_closed, exit_price
- SizePositionCommand.metrics: Optional[StrategyMetrics] ไม่ใช่ dict

วิธีแก้: เก็บ pattern_id ใน module-level dict keyed by symbol
         เพราะบอทเปิดได้ max 1 position ต่อ symbol
"""
import logging
import json
import os
import threading
from datetime import datetime
from typing import Optional
import pandas as pd

logger = logging.getLogger("GQOS.OutcomeLogger")

OUTCOMES_PATH = "data/learning/live_outcomes.jsonl"
PENDING_PATH  = "data/learning/pending_trades.json"


class TradeOutcomeLogger:
    def __init__(self):
        os.makedirs("data/learning", exist_ok=True)
        # key = symbol (e.g. "XAUUSD"), value = trade metadata
        self._pending: dict = self._load_pending()
        self._lock = threading.Lock()
        logger.info(f"OutcomeLogger ready. Pending: {len(self._pending)}")

    # ── เรียกตอนเปิด position ─────────────────────────────────────────
    def on_trade_opened(
        self,
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
        with self._lock:
            self._pending[symbol] = {
                "symbol":             symbol,
                "direction":          direction,
                "entry_price":        entry_price,
                "sl_price":           sl_price,
                "tp_price":           tp_price,
                "pattern_id":         pattern_id,
                "pattern_pf":         pattern_pf,
                "pattern_similarity": pattern_sim,
                "session":            session,
                "strategy_id":        strategy_id,
                "open_time":          datetime.utcnow().isoformat(),
            }
            self._save_pending()
            logger.info(
                f"[OutcomeLogger] Opened: {symbol} {direction} "
                f"pattern={pattern_id} pf={pattern_pf:.2f}"
            )

    # ── เรียกตอนปิด position ──────────────────────────────────────────
    def on_trade_closed(
        self,
        symbol: str,
        realized_pnl: float,
        exit_price: float = 0.0,
    ):
        with self._lock:
            meta = self._pending.pop(symbol, None)
            if meta is None:
                # ยังไม่รู้ pattern เพราะ trade เปิดก่อน logger จะพร้อม
                meta = {"symbol": symbol, "pattern_id": None,
                        "pattern_pf": 0.0, "session": "Unknown",
                        "strategy_id": "unknown", "entry_price": 0.0,
                        "sl_price": 0.0, "direction": "UNKNOWN"}

            sl_dist   = abs(meta["entry_price"] - meta["sl_price"])
            actual_r  = round(realized_pnl / (sl_dist * 100), 3) if sl_dist > 0 else None
            outcome   = "WIN" if realized_pnl > 0 else "LOSS"

            record = {
                **meta,
                "exit_price":   exit_price,
                "realized_pnl": realized_pnl,
                "actual_r":     actual_r,
                "outcome":      outcome,
                "close_time":   datetime.utcnow().isoformat(),
            }

            with open(OUTCOMES_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            self._save_pending()
            logger.info(
                f"[OutcomeLogger] Closed: {symbol} {outcome} "
                f"pnl={realized_pnl:.2f} R={actual_r} "
                f"pattern={meta['pattern_id']}"
            )
            return record

    # ── helpers ──────────────────────────────────────────────────────
    def get_outcomes_df(self) -> pd.DataFrame:
        if not os.path.exists(OUTCOMES_PATH):
            return pd.DataFrame()
        rows = []
        with open(OUTCOMES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return pd.DataFrame(rows)

    def get_stats(self) -> dict:
        df = self.get_outcomes_df()
        if df.empty:
            return {"total": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "total_pnl": 0.0}
        wins  = len(df[df["outcome"] == "WIN"])
        total = len(df)
        return {
            "total":     total,
            "wins":      wins,
            "losses":    total - wins,
            "win_rate":  round(wins / total * 100, 1),
            "total_pnl": round(df["realized_pnl"].sum(), 2),
            "avg_r":     round(df["actual_r"].dropna().mean(), 3) if "actual_r" in df else 0.0,
        }

    def _load_pending(self) -> dict:
        if os.path.exists(PENDING_PATH):
            try:
                with open(PENDING_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_pending(self):
        with open(PENDING_PATH, "w") as f:
            json.dump(self._pending, f, indent=2)


outcome_logger = TradeOutcomeLogger()
