from typing import Tuple, List
from decimal import Decimal
from .models import RiskBudget, AllocationRequest, AllocationResult
from .store import RiskBudgetStore

class RiskBudgetEngine:
    """
    Deterministic domain service for evaluating allocation requests against risk budgets.
    Delegates atomic evaluation to the store.
    """
    def __init__(self, store: RiskBudgetStore):
        self._store = store

    def request_allocation(self, request: AllocationRequest) -> Tuple[AllocationResult, RiskBudget, List[Decimal]]:
        """
        Evaluates an allocation request.
        Returns the AllocationResult, the updated RiskBudget, and a list of near-limit thresholds crossed (if any).
        """
        return self._store.allocate(request)

    def release_allocation(self, allocation_id: str) -> Tuple[bool, RiskBudget, Decimal]:
        """
        Releases utilized capacity back to the budget using allocation_id.
        """
        return self._store.release(allocation_id)

class CircuitBreakerEngine:
    def __init__(self):
        import threading
        from .circuit_breaker import CircuitState, CircuitBreaker, CircuitBreakerSnapshot
        self._breakers = {}
        self._snapshots = {}
        self._lock = threading.RLock()
        
    def trip(self, breaker_id: str, reason: str) -> bool:
        """Trips a circuit breaker to OPEN."""
        with self._lock:
            from .circuit_breaker import CircuitState, CircuitBreaker, CircuitBreakerSnapshot
            import time
            current = self._breakers.get(breaker_id, CircuitBreaker(breaker_id=breaker_id))
            if current.state == CircuitState.OPEN:
                return False
                
            new_version = current.version + 1
            self._breakers[breaker_id] = CircuitBreaker(
                breaker_id=breaker_id,
                state=CircuitState.OPEN,
                tripped_reason=reason,
                tripped_at=time.time(),
                version=new_version
            )
            self._snapshots[breaker_id] = CircuitBreakerSnapshot(
                breaker_id=breaker_id,
                state=CircuitState.OPEN,
                version=new_version,
                parent_version=current.version
            )
            return True
            
    def half_open(self, breaker_id: str) -> bool:
        """Sets a circuit breaker to HALF_OPEN for testing."""
        with self._lock:
            from .circuit_breaker import CircuitState, CircuitBreaker, CircuitBreakerSnapshot
            current = self._breakers.get(breaker_id, CircuitBreaker(breaker_id=breaker_id))
            if current.state != CircuitState.OPEN:
                return False
                
            new_version = current.version + 1
            self._breakers[breaker_id] = CircuitBreaker(
                breaker_id=current.breaker_id,
                state=CircuitState.HALF_OPEN,
                tripped_reason=current.tripped_reason,
                tripped_at=current.tripped_at,
                version=new_version
            )
            self._snapshots[breaker_id] = CircuitBreakerSnapshot(
                breaker_id=breaker_id,
                state=CircuitState.HALF_OPEN,
                version=new_version,
                parent_version=current.version
            )
            return True

    def reset(self, breaker_id: str) -> bool:
        """Resets a circuit breaker to CLOSED."""
        with self._lock:
            from .circuit_breaker import CircuitState, CircuitBreaker, CircuitBreakerSnapshot
            current = self._breakers.get(breaker_id, CircuitBreaker(breaker_id=breaker_id))
            if current.state == CircuitState.CLOSED:
                return False
                
            new_version = current.version + 1
            self._breakers[breaker_id] = CircuitBreaker(
                breaker_id=breaker_id,
                state=CircuitState.CLOSED,
                version=new_version
            )
            self._snapshots[breaker_id] = CircuitBreakerSnapshot(
                breaker_id=breaker_id,
                state=CircuitState.CLOSED,
                version=new_version,
                parent_version=current.version
            )
            return True

    def is_tripped(self, breaker_id: str) -> bool:
        """Returns True if the circuit breaker is OPEN or HALF_OPEN."""
        with self._lock:
            from .circuit_breaker import CircuitState, CircuitBreaker
            current = self._breakers.get(breaker_id, CircuitBreaker(breaker_id=breaker_id))
            return current.state in (CircuitState.OPEN, CircuitState.HALF_OPEN)
            
    def rebuild_from_events(self, events: list):
        """Rebuilds state from an event stream to survive restarts."""
        from .events import CircuitBreakerTripped, CircuitBreakerReset, CircuitBreakerHalfOpened
        with self._lock:
            for env in events:
                payload = env.payload
                if isinstance(payload, CircuitBreakerTripped):
                    self.trip(payload.breaker_id, payload.reason)
                elif isinstance(payload, CircuitBreakerHalfOpened):
                    self.half_open(payload.breaker_id)
                elif isinstance(payload, CircuitBreakerReset):
                    self.reset(payload.breaker_id)
