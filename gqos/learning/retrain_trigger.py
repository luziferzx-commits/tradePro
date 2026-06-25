"""
gqos/learning/retrain_trigger.py

Auto-Retrain Trigger — trigger การ retrain ML models อัตโนมัติ
เมื่อมี live trade outcomes ใหม่เพียงพอ

Flow:
  ทุก trade ที่ปิด → เช็คว่ามี new trades ถึง threshold ไหม
  ถ้าถึง → trigger retrain ใน background thread
  หลัง retrain → reload model ใน MLPredictor
  บอทฉลาดขึ้นโดยอัตโนมัติ ไม่ต้อง restart
"""
import logging
import threading
import os
import json
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger("GQOS.RetrainTrigger")

RETRAIN_STATE_PATH = "data/learning/retrain_state.json"


class AutoRetrainTrigger:
    """
    Monitor จำนวน live trades และ trigger retrain อัตโนมัติ
    """

    def __init__(
        self,
        retrain_threshold: int = 50,
        min_win_rate: float = 0.35,
        on_retrain_complete: Optional[Callable] = None,
    ):
        """
        retrain_threshold: จำนวน new live trades ที่ต้องการก่อน retrain
        min_win_rate: win rate ขั้นต่ำ ถ้าต่ำกว่านี้จะ alert ไม่ retrain
        on_retrain_complete: callback หลัง retrain เสร็จ (เช่น reload model)
        """
        self.retrain_threshold = retrain_threshold
        self.min_win_rate = min_win_rate
        self.on_retrain_complete = on_retrain_complete
        self._state = self._load_state()
        self._lock = threading.Lock()
        self._is_retraining = False

        logger.info(
            f"[RetrainTrigger] Initialized. "
            f"Threshold={retrain_threshold} trades. "
            f"Trades since last retrain: {self._state['trades_since_retrain']}"
        )

    def on_trade_closed(self, outcome: str, symbol: str, realized_pnl: float):
        """
        เรียกทุกครั้งที่ trade ปิด
        เช็คว่าถึงเวลา retrain หรือยัง
        """
        with self._lock:
            self._state["trades_since_retrain"] += 1
            self._state["total_live_trades"] += 1

            if outcome == "WIN":
                self._state["wins_since_retrain"] += 1
            self._state["pnl_since_retrain"] += realized_pnl

            self._save_state()

            current = self._state["trades_since_retrain"]
            logger.debug(
                f"[RetrainTrigger] {symbol} {outcome} | "
                f"Progress: {current}/{self.retrain_threshold}"
            )

            # Check if should retrain
            if current >= self.retrain_threshold and not self._is_retraining:
                self._maybe_trigger_retrain()

    def _maybe_trigger_retrain(self):
        """ตัดสินใจว่าจะ retrain หรือไม่"""
        trades = self._state["trades_since_retrain"]
        wins = self._state["wins_since_retrain"]
        win_rate = wins / trades if trades > 0 else 0.0
        pnl = self._state["pnl_since_retrain"]

        logger.info(
            f"[RetrainTrigger] Checking retrain criteria: "
            f"trades={trades} wr={win_rate:.1%} pnl={pnl:.2f}"
        )

        if win_rate < self.min_win_rate:
            logger.warning(
                f"[RetrainTrigger] Win rate {win_rate:.1%} < {self.min_win_rate:.1%}. "
                f"Model performance degraded. Triggering retrain for recovery."
            )

        # Trigger retrain in background
        logger.info("[RetrainTrigger] 🔄 Triggering background retrain...")
        self._is_retraining = True
        thread = threading.Thread(
            target=self._run_retrain,
            daemon=True,
            name="RetainWorker"
        )
        thread.start()

    def _run_retrain(self):
        """รัน retrain pipeline ใน background"""
        try:
            logger.info("[RetrainTrigger] Starting retrain pipeline...")

            # 1. Update pattern confidence ก่อน
            from gqos.learning.outcome_logger import outcome_logger
            from gqos.learning.pattern_updater import pattern_updater

            outcomes_df = outcome_logger.get_outcomes_df()
            if not outcomes_df.empty:
                result = pattern_updater.update(outcomes_df)
                logger.info(f"[RetrainTrigger] Pattern update: {result}")

            # 2. Retrain ML models
            from data.mt5_client import mt5_client
            from ml.dataset_builder import build_dataset
            from mlops.train_production import train_and_register_production

            # Retrain symbols ที่มี live data เพียงพอ
            symbols_with_data = (
                outcomes_df.groupby("symbol").size()
                if not outcomes_df.empty
                else {}
            )

            for symbol, count in (
                symbols_with_data.items()
                if hasattr(symbols_with_data, "items")
                else []
            ):
                if count < 20:
                    continue
                try:
                    logger.info(f"[RetrainTrigger] Retraining {symbol} ({count} live trades)...")
                    dataset_path = build_dataset(symbol, "M5", atr_multiplier=2.0)
                    if dataset_path and os.path.exists(dataset_path):
                        version = train_and_register_production(
                            symbol, dataset_path, status="production"
                        )
                        logger.info(f"[RetrainTrigger] {symbol} retrained: {version}")
                except Exception as e:
                    logger.error(f"[RetrainTrigger] Error retraining {symbol}: {e}")

            # 3. Reset counters
            with self._lock:
                self._state["trades_since_retrain"] = 0
                self._state["wins_since_retrain"] = 0
                self._state["pnl_since_retrain"] = 0.0
                self._state["last_retrain"] = datetime.utcnow().isoformat()
                self._save_state()

            logger.info("[RetrainTrigger] ✅ Retrain complete.")

            # 4. Callback (เช่น reload model ใน predictor)
            if self.on_retrain_complete:
                self.on_retrain_complete()

        except Exception as e:
            logger.error(f"[RetrainTrigger] Retrain failed: {e}", exc_info=True)
        finally:
            self._is_retraining = False

    def get_status(self) -> dict:
        return {
            **self._state,
            "is_retraining": self._is_retraining,
            "next_retrain_in": max(
                0, self.retrain_threshold - self._state["trades_since_retrain"]
            ),
        }

    def _load_state(self) -> dict:
        if os.path.exists(RETRAIN_STATE_PATH):
            try:
                with open(RETRAIN_STATE_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "trades_since_retrain": 0,
            "wins_since_retrain": 0,
            "pnl_since_retrain": 0.0,
            "total_live_trades": 0,
            "last_retrain": None,
        }

    def _save_state(self):
        os.makedirs("data/learning", exist_ok=True)
        with open(RETRAIN_STATE_PATH, "w") as f:
            json.dump(self._state, f, indent=2)


# Singleton
retrain_trigger = AutoRetrainTrigger(retrain_threshold=50)
