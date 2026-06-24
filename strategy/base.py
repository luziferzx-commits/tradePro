from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> str:
        """
        Analyzes the dataframe and current regime to return 'BUY', 'SELL', or 'NEUTRAL'
        """
        pass
