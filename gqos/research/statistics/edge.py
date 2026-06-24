from abc import ABC, abstractmethod
from typing import Dict
import numpy as np

class IEdgeScoreModel(ABC):
    @abstractmethod
    def calculate(self, metrics: Dict[str, float], campaign_percentiles: Dict[str, callable]) -> float:
        """
        Calculates the 0-100 Edge Score using percentiles.
        campaign_percentiles is a dictionary mapping metric_name -> function(value) -> percentile (0-100)
        """
        pass

class InstitutionalEdgeScore(IEdgeScoreModel):
    def calculate(self, metrics: Dict[str, float], campaign_percentiles: Dict[str, callable]) -> float:
        """
        25% Sharpe
        20% (1-PBO)
        20% (1-SPA_pvalue)
        15% Execution_Quality
        10% Capacity
        10% Stability
        """
        # Default percentile func returns 50 (median) if missing
        def get_pct(name, val):
            if name in campaign_percentiles:
                return campaign_percentiles[name](val)
            return 50.0

        sharpe_pct = get_pct('sharpe', metrics.get('sharpe', 0.0))
        
        # PBO is lower=better. So we invert it before percentiling, or assume percentile func handles it.
        # Let's assume percentile func handles lower=better correctly, returning higher percentile for lower PBO.
        pbo_pct = get_pct('pbo', metrics.get('pbo', 1.0))
        spa_pct = get_pct('spa', metrics.get('spa_pvalue', 1.0))
        
        exec_pct = get_pct('execution', metrics.get('execution_slippage_bps', 10.0))
        cap_pct = get_pct('capacity', metrics.get('capacity_usd', 0.0))
        stab_pct = get_pct('stability', metrics.get('stability', 0.0))
        
        score = (
            0.25 * sharpe_pct +
            0.20 * pbo_pct +
            0.20 * spa_pct +
            0.15 * exec_pct +
            0.10 * cap_pct +
            0.10 * stab_pct
        )
        return float(np.clip(score, 0, 100))
