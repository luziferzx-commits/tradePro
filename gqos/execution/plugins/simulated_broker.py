import time
from typing import List, Type
from gqos.execution.plugin import IPlugin
from gqos.messaging.contracts import Command, MessageEnvelope
from gqos.execution.messages import ExecuteTradeCommand, TradeExecutedEvent
from gqos.domain.models.execution import Trade
from gqos.domain.value_objects import Price, LotSize

class SimulatedBrokerPlugin(IPlugin):
    def supported_commands(self) -> List[Type[Command]]:
        return [ExecuteTradeCommand]
        
    def handle(self, envelope: MessageEnvelope[ExecuteTradeCommand], bus) -> None:
        cmd = envelope.payload
        decision = cmd.decision
        
        # Simulate execution delay
        time.sleep(0.01)
        
        # Execute trade
        trade = Trade(
            symbol=decision.prediction.dataset.symbol,
            entry_price=Price(1900.50), # Simulated fill price
            lot_size=LotSize(1.0),      # Simulated fill volume
            decision=decision,
            timestamp=time.time()
        )
        
        # Emit the event via EventBus. 
        # Crucial Rule 6: Plugin ห้ามเข้าถึง ArtifactRegistry โดยตรง (No direct Registry access)
        event = TradeExecutedEvent(trade=trade)
        
        # Maintain correlation ID for tracing from Command to Event
        event_env = MessageEnvelope.create(
            payload=event, 
            version=1, 
            correlation_id=envelope.correlation_id
        )
        bus.publish(event_env)
