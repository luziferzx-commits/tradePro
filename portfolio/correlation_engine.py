"""portfolio/correlation_engine.py"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

class CorrelationEngine:
    def __init__(self, config_path: str = "config/correlations.yaml", metadata=None):
        self.config_path = config_path
        self.correlations = {}
        self.metadata = metadata
        self.warnings = []
        self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            self.warnings.append("STATIC_CORRELATION_USED")
            logger.warning("STATIC_CORRELATION_USED: Correlation config not found, using conservative defaults.")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data and "correlations" in data:
            self.correlations = data["correlations"]
            self.warnings.append("STATIC_CORRELATION_USED")
            logger.warning("STATIC_CORRELATION_USED: Using static predefined correlations.")

    def get_correlation(self, sym1: str, sym2: str) -> float:
        if sym1 == sym2:
            return 1.0
            
        key1 = f"{sym1}_{sym2}"
        key2 = f"{sym2}_{sym1}"
        
        if key1 in self.correlations:
            return self.correlations[key1]
        if key2 in self.correlations:
            return self.correlations[key2]
            
        # Fallback conservative defaults
        if self.metadata:
            class1 = self.metadata.get_asset_class(sym1)
            class2 = self.metadata.get_asset_class(sym2)
            if class1 == class2 and class1 != "UNKNOWN":
                return 0.60 # Same asset class
                
        return 0.25 # Cross asset

    def calculate_correlation_penalty(self, candidate_symbol: str, candidate_side: str, open_positions: list[dict]) -> tuple[float, list[str]]:
        """
        Calculates a risk penalty multiplier [0.0, 1.0].
        Returns (multiplier, reduction_reasons)
        """
        max_penalty = 0.0
        reasons = []
        
        for pos in open_positions:
            pos_symbol = pos.get("symbol")
            pos_side = pos.get("side")
            
            corr = self.get_correlation(candidate_symbol, pos_symbol)
            
            is_same_direction = (candidate_side == pos_side)
            effective_corr = corr if is_same_direction else -corr
            
            if effective_corr > 0.6:
                penalty = effective_corr
                if penalty > max_penalty:
                    max_penalty = penalty
                reasons.append(f"Correlated with {pos_symbol} ({effective_corr:.2f})")
                    
        return 1.0 - max_penalty, reasons
