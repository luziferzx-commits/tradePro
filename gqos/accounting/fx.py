from abc import ABC, abstractmethod
from decimal import Decimal

class IFxConverter(ABC):
    @abstractmethod
    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        pass

class MockFxConverter(IFxConverter):
    def convert(self, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
        # 1:1 conversion for M10A
        return amount
