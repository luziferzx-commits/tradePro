import uuid
import logging
from decimal import Decimal
from typing import Dict
from dataclasses import dataclass, field

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import OrderStatus, OrderUpdateEvent
from gqos.common.enums import TradeDirection
from gqos.risk.events import TradeExecutedEvent

logger = logging.getLogger(__name__)

@dataclass
class LiveOrder:
    order_id: str
    symbol: str
    direction: TradeDirection
    total_quantity: Decimal
    stop_loss: Decimal = Decimal('0')
    take_profit: Decimal = Decimal('0')
    filled_quantity: Decimal = Decimal('0')
    remaining_quantity: Decimal = field(init=False)
    status: OrderStatus = OrderStatus.NEW
    average_fill_price: Decimal = Decimal('0')
    strategy_id: str = "global"
    risk_allocation_id: str = ""
    portfolio_allocation_id: str = ""
    
    def __post_init__(self):
        self.remaining_quantity = self.total_quantity

class OrderManagementSystem:
    def __init__(self, event_bus: IEventBus):
        self._event_bus = event_bus
        self.orders: Dict[str, LiveOrder] = {}
        
    def create_order(
        self,
        symbol: str,
        direction: TradeDirection,
        quantity: Decimal,
        strategy_id: str = "global",
        risk_allocation_id: str = "",
        portfolio_allocation_id: str = "",
        stop_loss: Decimal = Decimal('0'),
        take_profit: Decimal = Decimal('0'),
    ) -> str:
        order_id = str(uuid.uuid4())
        order = LiveOrder(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            total_quantity=quantity,
            stop_loss=stop_loss or Decimal('0'),
            take_profit=take_profit or Decimal('0'),
            strategy_id=strategy_id,
            risk_allocation_id=risk_allocation_id,
            portfolio_allocation_id=portfolio_allocation_id,
        )
        self.orders[order_id] = order
        self._emit_update(order)
        return order_id
        
    def update_order_status(self, order_id: str, new_status: OrderStatus, message: str = ""):
        if order_id not in self.orders:
            logger.warning("OMS status update ignored for unknown order_id=%s status=%s message=%s", order_id, new_status, message)
            return
        order = self.orders[order_id]
        order.status = new_status
        self._emit_update(order, message)
        
    def apply_fill(self, order_id: str, fill_qty: Decimal, fill_price: Decimal, message: str = ""):
        """
        Called when a partial or full fill arrives from the broker.
        """
        if order_id not in self.orders:
            logger.warning("OMS fill ignored for unknown order_id=%s message=%s", order_id, message)
            return
            
        order = self.orders[order_id]
        
        if order.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED, OrderStatus.FILLED]:
            return # Terminal state
            
        order.filled_quantity += fill_qty
        order.remaining_quantity = order.total_quantity - order.filled_quantity
        total_value = (order.average_fill_price * (order.filled_quantity - fill_qty)) + (fill_qty * fill_price)
        if order.filled_quantity > Decimal('0'):
            order.average_fill_price = total_value / order.filled_quantity
            
        if order.remaining_quantity <= Decimal('0'):
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL
            
        self._emit_update(order)
        
        ticket_str = order.order_id
        if message:
            if "MT5 Ticket:" in message:
                ticket_str = message.split("MT5 Ticket:", 1)[1].strip()
            elif "MT5 Limit Filled:" in message:
                ticket_str = message.split("MT5 Limit Filled:", 1)[1].strip()

        # Emit TradeExecutedEvent so Accounting / Portfolio immediately update
        trade_evt = TradeExecutedEvent(
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=fill_qty,
            execution_price=fill_price,
            intended_price=fill_price, # We ignore slippage here, it's baked into fill_price
            slippage_amount=Decimal('0'),
            ticket=ticket_str,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )
        self._event_bus.publish(MessageEnvelope.create(payload=trade_evt, version=1))
        
    def _emit_update(self, order: LiveOrder, message: str = ""):
        evt = OrderUpdateEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            status=order.status,
            filled_quantity=order.filled_quantity,
            remaining_quantity=order.remaining_quantity,
            average_fill_price=order.average_fill_price,
            message=message,
            risk_allocation_id=order.risk_allocation_id,
            portfolio_allocation_id=order.portfolio_allocation_id,
        )
        self._event_bus.publish(MessageEnvelope.create(payload=evt, version=1))
