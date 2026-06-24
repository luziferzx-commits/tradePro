# ADR-0010: Circuit Breaker & M7A Concurrency Resolution

## Status
Approved

## Context
With the introduction of the Risk Budget Engine (M7A), several technical limitations were identified by the Chief Quant Architect:
1. **Race Conditions**: Parallel threads executing `request_allocation` could bypass limits due to non-atomic read-then-write operations.
2. **Financial Math Inaccuracies**: Using `float` introduces rounding errors unsuitable for a production risk system.
3. **Fail-Safes**: The system lacked an overarching Circuit Breaker (M7B) to halt trading upon extreme conditions (e.g., Daily Loss Limit).

## Decisions

### 1. Store-Level Locking (Option A)
We moved the allocation logic directly into `RiskBudgetStore.allocate()`.
- **Rationale**: For an in-memory store, executing read, evaluate, and write under a single `RLock` ensures strict atomicity without the complexity of Optimistic Concurrency Control (CAS) and retry loops.

### 2. Decimal Type for Financial Logic
All financial amounts (`requested_amount`, `capacity`, `estimated_value`) were migrated from `float` to `decimal.Decimal`.
- **Rationale**: Precision is critical. `Decimal` prevents floating-point drift over millions of operations.

### 3. Circuit Breaker Triggering via Command
We separated the responsibility of monitoring from the state management of the Circuit Breaker.
- **Decision**: A `RiskMonitor` (to be fully implemented later) will emit a `TripCircuitBreakerCommand`. The `CircuitBreakerEngine` acts strictly on these commands.
- **Rationale**: Keeps the Circuit Breaker decoupled from raw `TradeExecutedEvent`s, maintaining single-responsibility and preventing the breaker from mixing monitoring logic with state transitioning logic.

### 4. Circuit Breaker as Primary Gatekeeper
The `RiskGuardedCommandBus` was updated to check the `CircuitBreakerEngine` *before* the `RiskBudgetEngine`.
- **Rationale**: If the system is in an emergency state (TRIPPED), calculating allocations is unnecessary. The breaker takes precedence.

## Consequences
- The platform is now thread-safe against concurrent risk allocation bursts.
- Precision errors are eliminated.
- The `RiskGuardedCommandBus` correctly halts all execution attempts when a Circuit Breaker is tripped, emitting a `TradeRejectedByCircuitBreaker` event.
