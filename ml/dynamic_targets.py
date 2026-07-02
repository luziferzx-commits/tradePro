import os
import logging
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from config.settings import settings

logger = logging.getLogger("GQOS.DynamicTargets")

class DynamicTargetPredictor:
    """
    Predicts optimal SL/TP distances based on historical live outcomes.
    If insufficient data is available, returns the static default buffers.
    """
    def __init__(self, min_samples=None, allowed_sources=None):
        self._model_sl = None
        self._model_tp = None
        self._min_samples = int(min_samples or settings.DYNAMIC_TARGET_MIN_SAMPLES)
        raw_sources = allowed_sources or settings.LEARNING_ALLOWED_SOURCES
        self._allowed_sources = {s.strip().upper() for s in str(raw_sources).split(",") if s.strip()}
        self._is_trained = False
        self._train_if_needed()

    @property
    def is_trained(self) -> bool:
        return self._is_trained
        
    def _train_if_needed(self):
        try:
            from gqos.learning.outcome_logger import outcome_logger
            df = outcome_logger.get_outcomes_df(allowed_sources=self._allowed_sources)
            if not df.empty:
                self.train(df)
        except Exception as e:
            logger.warning(f"[DynamicTargets] Auto-train failed: {e}")

    def train(self, outcomes_df: pd.DataFrame):
        if not outcomes_df.empty and "source" in outcomes_df.columns:
            outcomes_df = outcomes_df[
                outcomes_df["source"].fillna("LIVE").astype(str).str.upper().isin(self._allowed_sources)
            ]

        if outcomes_df.empty or len(outcomes_df) < self._min_samples:
            logger.info(f"[DynamicTargets] Insufficient data to train ({len(outcomes_df)} < {self._min_samples}). Using static defaults.")
            return False
            
        if 'pattern_similarity' not in outcomes_df.columns:
            outcomes_df['pattern_similarity'] = outcomes_df.get('pattern_sim', 0.5)
            
        required = {'entry_price', 'sl_price', 'tp_price'}
        if not required.issubset(set(outcomes_df.columns)):
            logger.info("[DynamicTargets] Missing entry/sl/tp columns. Using static defaults.")
            return False
            
        # Target variables are price-distance buffers. We do not train on raw
        # realized PnL because that is in account currency, not price units.
        sl_distance = (outcomes_df['entry_price'] - outcomes_df['sl_price']).abs()
        tp_distance = (outcomes_df['tp_price'] - outcomes_df['entry_price']).abs()
        valid = (sl_distance > 0) & (tp_distance > 0)
        if valid.sum() < self._min_samples:
            logger.info(f"[DynamicTargets] Insufficient valid target rows ({valid.sum()} < {self._min_samples}). Using static defaults.")
            return False

        X = outcomes_df[['pattern_similarity']].fillna(0.5)
        X = X.loc[valid]
        y_sl = sl_distance.loc[valid]
        y_tp = tp_distance.loc[valid]
        
        self._model_sl = RandomForestRegressor(n_estimators=10, max_depth=3, random_state=42)
        self._model_tp = RandomForestRegressor(n_estimators=10, max_depth=3, random_state=43)
        self._model_sl.fit(X, y_sl)
        self._model_tp.fit(X, y_tp)
        self._is_trained = True
        logger.info(f"[DynamicTargets] Trained successfully on {len(X)} trades.")
        return True

    def predict(self, pattern_sim: float, default_sl_buffer: float) -> tuple[float, float]:
        """
        Returns (predicted_sl_buffer, predicted_tp_buffer)
        Uses hard bounds enforced by caller.
        """
        if not self._is_trained:
            return default_sl_buffer, default_sl_buffer * 2.0
            
        try:
            X = pd.DataFrame([{"pattern_similarity": pattern_sim}])
            pred_sl = float(self._model_sl.predict(X)[0])
            pred_sl = max(pred_sl, 0.0001)
            pred_tp = float(self._model_tp.predict(X)[0]) if self._model_tp else pred_sl * 2.0
            pred_tp = max(pred_tp, pred_sl)
            return pred_sl, pred_tp
        except Exception as e:
            logger.error(f"[DynamicTargets] Prediction error: {e}")
            return default_sl_buffer, default_sl_buffer * 2.0

# Singleton
dynamic_targets = DynamicTargetPredictor()
