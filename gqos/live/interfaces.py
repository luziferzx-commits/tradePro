from abc import ABC, abstractmethod
from typing import Dict
from decimal import Decimal
from gqos.common.enums import TradeDirection

class IBrokerAdapter(ABC):
    @abstractmethod
    def start(self):
        """Starts background streams (e.g. websockets)"""
        pass
        
    @abstractmethod
    def stop(self):
        """Stops background streams"""
        pass
        
    @abstractmethod
    def submit_order(self, order_id: str, symbol: str, direction: TradeDirection, quantity: Decimal, price: Decimal):
        """Submits an order to the exchange, handling any lot/tick size adjustments internally."""
        pass
        
    @abstractmethod
    def cancel_order(self, order_id: str):
        """Cancels an existing order"""
        pass
        
    @abstractmethod
    def get_actual_positions(self) -> Dict[str, Decimal]:
        """Returns the current true positions held at the broker for reconciliation."""
        pass
