# ADR-0012: Exposure Engine (M7C)

## Status
Approved

## Context
With the Risk Budget Engine preventing over-allocation of capital and the Circuit Breaker protecting against catastrophic systemic risk, the system still lacked structural portfolio safeguards. For example, a strategy could allocate 100% of its budget into a single asset or sector, resulting in severe concentration risk. Before implementing mathematical Position Sizing (e.g., Kelly Criterion), an `ExposureEngine` was needed to act as a structural gatekeeper.

## Decisions

### 1. Static/Entry-based Exposure
We implemented an entry-based exposure calculation rather than full Mark-to-Market (MTM) streaming.
- **Rationale**: Introducing streaming market data events at this stage would add significant complexity. M7C focuses on establishing the architectural gatekeeper pattern. Exposure is calculated statically based on `quantity * execution_price` at the time of entry. True MTM dynamic exposure is deferred to a future phase (M7C.x). Note: The `estimated_value` used during `evaluate_trade()` is strictly an approximation, and final exposure is booked solely upon the reception of a `TradeExecutedEvent`.

### 2. Simplified Correlation Limits
Instead of a continuous covariance matrix calculation, we implemented "Correlation Groups" (e.g., "Tech-MegaCaps").
- **Rationale**: A mathematical covariance matrix requires a large rolling window of historical returns and a complex analytics service. By tagging assets into static correlation groups within an `AssetDirectory`, we achieve the same structural risk protection without the computational overhead. Future implementations will formalize CorrelationGroupID via UUIDs or Enums.

### 3. Delta-Based O(1) Evaluation (M7C.5)
The engine calculates projected exposure by adding the trade's delta directly to the current `gross_exposure` and `net_exposure` integers/decimals, rather than mutating or deep-copying a dictionary of positions.
- **Rationale**: A portfolio might contain 10,000+ positions. Deep copying `positions` for every `evaluate_trade()` call resulted in O(N) evaluations, creating a bottleneck. Delta-based evaluations perform in O(1) time (~3.2 µs), easily handling 100,000+ evaluations per second.

### 4. Immutable Snapshots & Event Sourcing (M7C.5)
The `ExposureState` was replaced with an immutable `@dataclass(frozen=True) ExposureSnapshot`. The `ExposureEngine` rebuilds its state entirely from `TradeExecutedEvent` streams.
- **Rationale**: Aligns the Exposure Engine with the platform's core CQRS/Event-Sourced philosophy. The immutable snapshot guarantees thread safety during read/evaluation, while `rebuild_from_events` guarantees resilience against crashes.

### 5. Evaluation Order
The `ExposureEngine` was inserted into the `RiskGuardedCommandBus` immediately after the `CircuitBreakerEngine` and before the `RiskBudgetEngine`.
- **Rationale**: If a trade violates portfolio structure (e.g., Sector Concentration limit breached), there is no need to perform atomic budget allocations. Blocking structural violations early saves resources and maintains clean budget states.

### 6. Unknown Symbol Rejection
If a symbol is not found in the `AssetDirectory`, the trade is automatically rejected.
- **Rationale**: A structural risk engine cannot evaluate risk without metadata (Sector, Correlation Group). Assuming a default sector like "UNKNOWN" bypasses sector concentration limits, which is unacceptable for production.

## Consequences
- The execution pipeline is now protected against Gross, Net, Symbol, Sector, and Correlation Group over-exposure.
- The system correctly blocks structural risks *before* budget allocation and plugin execution.
- `TradeRejectedByExposureLimit` events are reliably emitted for audit trails.
