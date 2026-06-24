from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict

class PricingUnavailableError(Exception):
    """Raised when the Market Data Provider cannot supply a price for a symbol."""
    pass

class IMarketDataProvider(ABC):
    @abstractmethod
    def get_latest_price(self, symbol: str) -> Decimal:
        """Returns the latest price for the given symbol."""
        pass

class MockMarketDataProvider(IMarketDataProvider):
    def __init__(self, prices: Dict[str, Decimal] = None):
        self.prices = prices or {}
        
    def get_latest_price(self, symbol: str) -> Decimal:
        if symbol not in self.prices:
            raise PricingUnavailableError(f"No mock price available for symbol: {symbol}")
        return self.prices[symbol]
        
    def update_price(self, symbol: str, price: Decimal):
        self.prices[symbol] = price

