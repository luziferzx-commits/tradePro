import time
import uuid
from gqos.messaging.contracts import MessageEnvelope, Command
from gqos.messaging.bus import ICommandBus, IEventBus
from .models import AllocationRequest
from .engine import RiskBudgetEngine, CircuitBreakerEngine
from .events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetExhausted, TradeRejectedByRiskEvent, TradeRejectedByCircuitBreaker, RiskBudgetNearLimit

class RiskGuardedCommandBus(ICommandBus):
    """
    Decorator for ICommandBus that acts as a gatekeeper for ExecuteTradeCommand.
    If the circuit breaker is tripped or budget is exceeded, the command is blocked.
    """
    def __init__(self, inner: ICommandBus, event_bus: IEventBus, engine: RiskBudgetEngine, cb_engine: CircuitBreakerEngine, exposure_engine=None):
        self._inner = inner
        self._event_bus = event_bus
        self._engine = engine
        self._cb_engine = cb_engine
        self._exposure_engine = exposure_engine
        
    def register_handler(self, command_type, handler) -> None:
        self._inner.register_handler(command_type, handler)
        
    def dispatch(self, envelope: MessageEnvelope[Command]):
        if isinstance(envelope.payload, ExecuteTradeCommand):
            trade_cmd = envelope.payload
            
            # 1. Check Circuit Breaker
            if self._cb_engine.is_tripped(trade_cmd.strategy_id):
                rejected_cb_evt = TradeRejectedByCircuitBreaker(
                    strategy_id=trade_cmd.strategy_id,
                    symbol=trade_cmd.symbol,
                    requested_value=trade_cmd.estimated_value,
                    reason="Circuit Breaker is TRIPPED"
                )
                self._event_bus.publish(
                    MessageEnvelope.create(
                        payload=rejected_cb_evt,
                        version=1,
                        correlation_id=envelope.correlation_id,
                        trace_id=envelope.trace_id
                    )
                )
                return None
                
            # 1.5 Check Exposure Limits
            if self._exposure_engine:
                success, limit_type, exp_reason = self._exposure_engine.evaluate_trade(trade_cmd)
                if not success:
                    from .events import TradeRejectedByExposureLimit
                    rejected_exp_evt = TradeRejectedByExposureLimit(
                        strategy_id=trade_cmd.strategy_id,
                        symbol=trade_cmd.symbol,
                        requested_value=trade_cmd.estimated_value,
                        limit_type=limit_type,
                        reason=exp_reason
                    )
                    self._event_bus.publish(
                        MessageEnvelope.create(
                            payload=rejected_exp_evt,
                            version=1,
                            correlation_id=envelope.correlation_id,
                            trace_id=envelope.trace_id
                        )
                    )
                    return None
            
            # 2. Check Risk Budget
            allocation_id = f"alloc-{envelope.correlation_id}-{trade_cmd.strategy_id}"
            request = AllocationRequest(
                allocation_id=allocation_id,
                budget_id=trade_cmd.strategy_id,
                strategy_id=trade_cmd.strategy_id,
                requested_amount=trade_cmd.estimated_value
            )
            
            result, budget, crossed_thresholds = self._engine.request_allocation(request)
            
            if result.success:
                allocated_evt = RiskBudgetAllocated(
                    budget_id=request.budget_id,
                    allocation_id=request.allocation_id,
                    strategy_id=request.strategy_id,
                    allocated_amount=result.amount_allocated,
                    new_utilized_capacity=budget.utilized_capacity,
                    total_capacity=budget.total_capacity
                )
                self._event_bus.publish(
                    MessageEnvelope.create(
                        payload=allocated_evt,
                        version=1,
                        correlation_id=envelope.correlation_id,
                        trace_id=envelope.trace_id
                    )
                )
                
                # Emit NearLimit events if applicable
                for t in crossed_thresholds:
                    near_limit_evt = RiskBudgetNearLimit(
                        budget_id=request.budget_id,
                        strategy_id=request.strategy_id,
                        utilized_percentage=t
                    )
                    self._event_bus.publish(
                        MessageEnvelope.create(
                            payload=near_limit_evt,
                            version=1,
                            correlation_id=envelope.correlation_id,
                            trace_id=envelope.trace_id
                        )
                    )
                
                try:
                    return self._inner.dispatch(envelope)
                except Exception as e:
                    # Compensation
                    rel_success, new_budget, released_amount = self._engine.release_allocation(allocation_id)
                    if rel_success:
                        from .events import RiskBudgetReleased
                        comp_evt = RiskBudgetReleased(
                            budget_id=request.budget_id,
                            allocation_id=allocation_id,
                            strategy_id=request.strategy_id,
                            released_amount=released_amount,
                            new_utilized_capacity=new_budget.utilized_capacity
                        )
                        self._event_bus.publish(
                            MessageEnvelope.create(
                                payload=comp_evt,
                                version=1,
                                correlation_id=envelope.correlation_id,
                                trace_id=envelope.trace_id
                            )
                        )
                    raise e
            else:
                exhausted_evt = RiskBudgetExhausted(
                    budget_id=request.budget_id,
                    strategy_id=request.strategy_id,
                    requested_amount=request.requested_amount,
                    current_utilized=budget.utilized_capacity if budget else 0.0,
                    total_capacity=budget.total_capacity if budget else 0.0,
                    reason=result.reason
                )
                rejected_evt = TradeRejectedByRiskEvent(
                    strategy_id=request.strategy_id,
                    symbol=trade_cmd.symbol,
                    requested_value=trade_cmd.estimated_value,
                    reason=result.reason
                )
                
                self._event_bus.publish(
                    MessageEnvelope.create(
                        payload=exhausted_evt,
                        version=1,
                        correlation_id=envelope.correlation_id,
                        trace_id=envelope.trace_id
                    )
                )
                
                self._event_bus.publish(
                    MessageEnvelope.create(
                        payload=rejected_evt,
                        version=1,
                        correlation_id=envelope.correlation_id,
                        trace_id=envelope.trace_id
                    )
                )
                return None
        else:
            return self._inner.dispatch(envelope)
