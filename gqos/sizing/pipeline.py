from decimal import Decimal
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.messaging.contracts import MessageEnvelope, Command
from gqos.sizing.events import SizePositionCommand, PositionSizedEvent, SizingFailedEvent
from gqos.risk.events import ExecuteTradeCommand
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.models import SizingRequest
from gqos.sizing.policies import ISizingPolicy
from gqos.sizing.portfolio import PortfolioSnapshot

class PositionSizingPipeline(ICommandBus):
    """
    Intercepts SizePositionCommand, calculates the position size via the PositionSizingEngine,
    and then forwards an ExecuteTradeCommand to the inner Risk bus.
    """
    
    def __init__(self, inner_bus: ICommandBus, event_bus: IEventBus, engine: PositionSizingEngine, policy: ISizingPolicy, portfolio: PortfolioSnapshot):
        self._inner_bus = inner_bus
        self._event_bus = event_bus
        self._engine = engine
        self._policy = policy
        self._portfolio = portfolio
        
    def dispatch(self, envelope: MessageEnvelope[Command]):
        if isinstance(envelope.payload, SizePositionCommand):
            cmd = envelope.payload
            
            # 1. Map to Request
            request = SizingRequest(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                direction=cmd.direction,
                entry_price=cmd.entry_price,
                stop_loss_price=cmd.stop_loss_price,
                conviction=cmd.conviction,
                metrics=cmd.metrics
            )
            
            # 2. Calculate Size
            try:
                result = self._engine.size_trade(request, self._policy, self._portfolio)
            except Exception as e:
                # Emit SizingFailedEvent
                failed_event = SizingFailedEvent(
                    strategy_id=cmd.strategy_id,
                    symbol=cmd.symbol,
                    direction=cmd.direction,
                    reason=str(e)
                )
                self._event_bus.publish(MessageEnvelope.create(
                    failed_event, 
                    version=envelope.version, 
                    correlation_id=envelope.correlation_id
                ))
                return None
            
            # 3. Publish Sized Event for Evidence
            sized_event = PositionSizedEvent(
                strategy_id=cmd.strategy_id,
                symbol=cmd.symbol,
                direction=cmd.direction,
                result=result,
                policy_name=self._policy.policy_name,
                policy_version=self._policy.policy_version,
                policy_parameters_hash=self._policy.policy_parameters_hash
            )
            self._event_bus.publish(MessageEnvelope.create(
                sized_event, 
                version=envelope.version, 
                correlation_id=envelope.correlation_id
            ))
            
            # 4. Generate ExecuteTradeCommand and forward
            execute_cmd = ExecuteTradeCommand(
                symbol=cmd.symbol,
                direction=cmd.direction,
                quantity=result.quantity,
                estimated_value=result.estimated_value,
                strategy_id=cmd.strategy_id
            )
            
            return self._inner_bus.dispatch(MessageEnvelope.create(
                execute_cmd,
                version=envelope.version,
                correlation_id=envelope.correlation_id
            ))
                
        else:
            # Pass through other commands
            return self._inner_bus.dispatch(envelope)

    def register_handler(self, command_type, handler) -> None:
        self._inner_bus.register_handler(command_type, handler)
