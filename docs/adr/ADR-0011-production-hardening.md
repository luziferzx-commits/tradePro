# ADR-0011: M7B.5 Production Hardening

## Status
Approved

## Context
Following the implementation of the M7B Circuit Breaker, a thorough architectural review revealed several gaps in production readiness. Specifically, the system lacked robustness against process restarts (lost circuit breaker state), near-limit event spam (hysteresis), and partial execution failures (inconsistent state). The `allocation_id` was also generated non-deterministically, compromising audit replays.

## Decisions

### 1. Circuit Breaker Event Sourcing
We introduced a `CircuitBreakerSnapshot` model along with a suite of commands/events (`ResetCircuitBreakerCommand`, `CircuitBreakerHalfOpened`, etc.).
- **Rationale**: The `CircuitBreakerEngine` is now capable of rebuilding its entire state machine (`CLOSED` -> `OPEN` -> `HALF_OPEN`) from the `EventStore`. This ensures that if the system crashes while the breaker is tripped, the state is fully recovered on restart.

### 2. Deterministic Allocation IDs
The `uuid.uuid4()` call in `RiskGuardedCommandBus` was replaced with a string interpolation of `correlation_id` and `strategy_id`.
- **Rationale**: Generating IDs dynamically broke deterministic replays. Tying the ID to the context guarantees that replays and live runs share the same audit trail.

### 3. Near-Limit Hysteresis
We added `emitted_thresholds: frozenset[Decimal]` to `RiskBudget`. The `RiskBudgetStore` calculates thresholds and prevents re-emission unless the utilization drops at least 5% below the crossed threshold.
- **Rationale**: Financial markets oscillate. Without hysteresis, a strategy hovering at 89.9% and 90.1% would trigger thousands of 90% threshold events, overwhelming monitoring systems.

### 4. Compensation Transactions (Decorator)
The `RiskGuardedCommandBus.dispatch()` method was updated to use a `try...except` block when calling the inner bus.
- **Rationale**: If the inner bus (or the target plugin) fails to execute the trade, the budget allocation must be unwound. Catching the exception, executing `engine.release_allocation()`, emitting a `RiskBudgetReleased` event, and then re-raising the exception prevents "leaking" budget on failed trades.

## Consequences
- Circuit Breaker state survives catastrophic crashes.
- Event spam is eliminated.
- Budgets accurately reflect real execution due to robust compensation.
- The system remains hyper-performant (latency benchmarks confirm overhead is strictly in the microsecond range).
