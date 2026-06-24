from abc import ABC, abstractmethod
import pandas as pd

class BaseSetupEvaluator(ABC):
    """Base interface for all market-specific strategy evaluators."""
    
    @abstractmethod
    def evaluate_all(self, df: pd.DataFrame, regime: dict, h4_trend: str = "NEUTRAL") -> list[dict]:
        """
        Evaluates data and returns a list of setup diagnostic dictionaries.
        Each dictionary should contain:
        - setup_name: str
        - score: float (-100 to 100)
        - direction: str ("BUY", "SELL", "NEUTRAL")
        - reason: str
        """
        pass
