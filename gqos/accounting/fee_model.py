from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Tuple
from gqos.common.enums import TradeDirection

class IFeeModel(ABC):
    @abstractmethod
    def calculate_fee(self, symbol: str, direction: TradeDirection, quantity: Decimal, execution_price: Decimal) -> Tuple[Decimal, str]:
        """
        Returns (fee_amount, currency)
        """
        pass

class MockFeeModel(IFeeModel):
    def __init__(self, commission_per_share: Decimal = Decimal('0.01'), currency: str = "USD"):
        self.commission_per_share = commission_per_share
        self.currency = currency
        
    def calculate_fee(self, symbol: str, direction: TradeDirection, quantity: Decimal, execution_price: Decimal) -> Tuple[Decimal, str]:
        fee = quantity * self.commission_per_share
        return fee, self.currency
