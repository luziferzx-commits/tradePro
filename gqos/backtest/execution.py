from decimal import Decimal
from typing import Callable
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.backtest.friction import ISlippageModel

class MockExecutionHandler:
    def __init__(self, event_bus: IEventBus, slippage_model: ISlippageModel, price_feed: Callable[[str], Decimal]):
        self._event_bus = event_bus
        self._slippage_model = slippage_model
        self._price_feed = price_feed
        
        self._event_bus.subscribe(ExecuteTradeCommand, self._handle_execute_command)
        
    def _handle_execute_command(self, envelope: MessageEnvelope[ExecuteTradeCommand]):
        cmd = envelope.payload
        
        # Get current market price
        market_price = self._price_feed(cmd.symbol)
        
        # Apply slippage
        executed_price = self._slippage_model.apply_slippage(cmd.direction, market_price, cmd.quantity)
        
        # Publish TradeExecutedEvent
        # Assuming the execution is instantaneous and fully filled in the backtest
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
            correlation_id=envelope.correlation_id
        ))
