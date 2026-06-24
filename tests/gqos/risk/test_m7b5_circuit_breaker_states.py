from gqos.risk.engine import CircuitBreakerEngine
from gqos.risk.circuit_breaker import CircuitState

def test_circuit_breaker_state_machine():
    engine = CircuitBreakerEngine()
    
    # 1. Starts CLOSED
    assert not engine.is_tripped("breaker_1")
    
    # 2. Trip to OPEN
    engine.trip("breaker_1", "Testing")
    assert engine.is_tripped("breaker_1")
    snapshot = engine._snapshots["breaker_1"]
    assert snapshot.state == CircuitState.OPEN
    assert snapshot.version == 2
    
    # 3. Half-Open
    engine.half_open("breaker_1")
    assert engine.is_tripped("breaker_1") # Half-open still blocks normal traffic except tests
    snapshot = engine._snapshots["breaker_1"]
    assert snapshot.state == CircuitState.HALF_OPEN
    assert snapshot.version == 3
    
    # 4. Reset to CLOSED
    engine.reset("breaker_1")
    assert not engine.is_tripped("breaker_1")
    snapshot = engine._snapshots["breaker_1"]
    assert snapshot.state == CircuitState.CLOSED
    assert snapshot.version == 4

if __name__ == "__main__":
    test_circuit_breaker_state_machine()
    print("Circuit breaker state machine test passed!")
