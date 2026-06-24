from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Optional

class IFactorModel(ABC):
    @abstractmethod
    def get_factor_exposures(self, symbol: str) -> Dict[str, Decimal]:
        """
        Returns a dictionary mapping factor names (e.g., 'Market', 'Value') 
        to the symbol's beta/exposure to that factor.
        """
        pass

class MockFactorModel(IFactorModel):
    def __init__(self, mappings: Dict[str, Dict[str, Decimal]] = None):
        self._mappings = mappings or {}

    def get_factor_exposures(self, symbol: str) -> Dict[str, Decimal]:
        # Return UNCLASSIFIED if not found
        return self._mappings.get(symbol, {"UNCLASSIFIED": Decimal('1.0')})
