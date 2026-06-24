from decimal import Decimal
from typing import List
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.backtest.friction import ISlippageModel
from gqos.paper.events import MarketDataEvent

class PaperExecutionHandler:
    def __init__(self, event_bus: IEventBus, slippage_model: ISlippageModel):
        self._event_bus = event_bus
        self._slippage_model = slippage_model
        
        self._order_queue: List[MessageEnvelope[ExecuteTradeCommand]] = []
        
        self._event_bus.subscribe(ExecuteTradeCommand, self._handle_execute_command)
        self._event_bus.subscribe(MarketDataEvent, self._handle_market_data)
        
    def _handle_execute_command(self, envelope: MessageEnvelope[ExecuteTradeCommand]):
        # Queue the order. Do NOT fill immediately to prevent lookahead bias.
        self._order_queue.append(envelope)
        
    def _handle_market_data(self, envelope: MessageEnvelope[MarketDataEvent]):
        if not self._order_queue:
            return
            
        tick = envelope.payload
        market_price = Decimal(str(tick.price))
        
        # We make a copy of the queue and clear it to simulate filling all pending
        pending_orders = self._order_queue.copy()
        self._order_queue.clear()
        
        for order_env in pending_orders:
            cmd = order_env.payload
            
            if cmd.symbol != tick.symbol:
                # If symbol doesn't match, push it back
                self._order_queue.append(order_env)
                continue
            
            # Apply slippage based on the NEW market price
            executed_price = self._slippage_model.apply_slippage(cmd.direction, market_price, cmd.quantity)
            
            event = TradeExecutedEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                direction=cmd.direction,
                quantity=cmd.quantity,
                execution_price=executed_price,
                intended_price=market_price,
                slippage_amount=abs(executed_price - market_price) * cmd.quantity
            )
            
            self._event_bus.publish(MessageEnvelope.create(
                payload=event,
                version=1,
                correlation_id=order_env.correlation_id
            ))
