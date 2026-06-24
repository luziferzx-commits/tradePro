from abc import ABC, abstractmethod
from decimal import Decimal
from gqos.common.enums import TradeDirection

class ISlippageModel(ABC):
    @abstractmethod
    def apply_slippage(self, direction: TradeDirection, price: Decimal, quantity: Decimal) -> Decimal:
        """Returns the final executed price after slippage."""
        pass

class FixedBpsSlippage(ISlippageModel):
    def __init__(self, bps: float = 1.0):
        self.bps = Decimal(str(bps / 10000.0))
        
    def apply_slippage(self, direction: TradeDirection, price: Decimal, quantity: Decimal) -> Decimal:
        # Buy higher, sell lower
        if direction == TradeDirection.BUY:
            return price * (Decimal('1') + self.bps)
        else:
            return price * (Decimal('1') - self.bps)

class ICommissionModel(ABC):
    @abstractmethod
    def calculate_commission(self, direction: TradeDirection, price: Decimal, quantity: Decimal) -> Decimal:
        pass

class FixedCommission(ICommissionModel):
    def __init__(self, per_unit_fee: float = 0.0):
        self.per_unit_fee = Decimal(str(per_unit_fee))
        
    def calculate_commission(self, direction: TradeDirection, price: Decimal, quantity: Decimal) -> Decimal:
        return quantity * self.per_unit_fee
