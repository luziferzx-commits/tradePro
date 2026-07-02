import json
import os
import logging

logger = logging.getLogger("MarketMemoryV2")

class MarketMemoryV2:
    def __init__(self, db_path="data/market_memory.json"):
        self.db_path = db_path
        self.memory = {}
        self.metadata = {}
        self.load()

    def load(self):
        if not os.path.exists(self.db_path):
            logger.warning(f"[MarketMemoryV2] DB not found at {self.db_path}. Memory is empty.")
            return

        try:
            with open(self.db_path, "r") as f:
                data = json.load(f)
                self.metadata = data.get("metadata", {})
                self.memory = data.get("memory", {})
            logger.info(f"[MarketMemoryV2] Loaded {len(self.memory)} context keys. Source: {self.metadata.get('source_file')}")
        except Exception as e:
            logger.error(f"[MarketMemoryV2] Failed to load {self.db_path}: {e}")

    def get_memory(self, session: str, regime: str, atr_bucket: str, direction: str) -> dict:
        """
        Retrieves the historical performance for the given context.
        Returns: {
            "memory_key": "...",
            "memory_matches": int,
            "memory_pf": float,
            "memory_win_rate": float,
            "memory_expectancy": float,
            "memory_confidence": str
        }
        """
        key = f"{session}|{regime}|{atr_bucket}|{direction}"
        data = self.memory.get(key)

        if not data:
            return {
                "memory_key": key,
                "memory_matches": 0,
                "memory_pf": 0.0,
                "memory_win_rate": 0.0,
                "memory_expectancy": 0.0,
                "memory_confidence": "UNKNOWN"
            }

        matches = data.get("matches", 0)
        pf = data.get("pf", 0.0)
        win_rate = data.get("win_rate", 0.0)
        expectancy = data.get("expectancy", 0.0)

        # Confidence Rules
        confidence = "LOW"
        if matches >= 30 and pf >= 1.5:
            confidence = "HIGH"
        elif matches >= 15 and pf >= 1.2:
            confidence = "MEDIUM"

        return {
            "memory_key": key,
            "memory_matches": matches,
            "memory_pf": pf,
            "memory_win_rate": win_rate,
            "memory_expectancy": expectancy,
            "memory_confidence": confidence
        }

# Global singleton
market_memory_v2 = MarketMemoryV2()
