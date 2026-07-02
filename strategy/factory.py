from strategy.setups.forex_metals import ForexMetalsEvaluator
from strategy.setups.crypto import CryptoEvaluator
from strategy.setups.base import BaseSetupEvaluator

class StrategyFactory:
    _instances = {}

    @classmethod
    def get_evaluator(cls, asset_class: str) -> BaseSetupEvaluator:
        """
        Returns the appropriate strategy evaluator based on asset class.
        Implements singleton pattern for evaluators to save memory.
        """
        asset_class = asset_class.upper() if asset_class else "FOREX"
        
        if asset_class not in cls._instances:
            if asset_class in ["CRYPTO"]:
                cls._instances[asset_class] = CryptoEvaluator()
            else:
                # Default for FOREX, METALS, INDICES
                cls._instances[asset_class] = ForexMetalsEvaluator()
                
        return cls._instances[asset_class]
