# ADR-0009: Risk Budget Engine & Gatekeeping Pattern

## Status
Approved

## Context
With the shift towards Phase 3 (Risk Platform), GQOS requires a centralized mechanism to prevent significant financial loss. The **Risk Budget Engine** is introduced as the first layer of defense (M7A) before any advanced algorithms (like Kelly or Circuit Breakers) are implemented. 

The core question was how the Risk Budget Engine should integrate with the `ExecutionPlatform` to gate trades.

Two patterns were considered:
- **Option A (Interceptor/Decorator)**: Implementing a `RiskGuardedCommandBus` that wraps the core `ICommandBus`. It intercepts `ExecuteTradeCommand`, requests an allocation from the `RiskBudgetEngine`, and blocks routing to the Plugin if denied.
- **Option B (Domain Service/Plugin Injection)**: Injecting `RiskBudgetEngine` into specific Plugins (e.g., `TradingPlugin`) and requiring the plugin to explicitly request budget before emitting execution events.

## Decision
We selected **Option A (Interceptor/Decorator Pattern)**.

### Rationale
1. **Platform-Level Gatekeeping**: Risk constraints must be enforced *before* execution logic. The broker plugin should not be responsible for deciding whether a trade passes risk checks.
2. **Deterministic Enforcement**: By enforcing this at the message bus level, we guarantee that no plugin can accidentally or maliciously bypass the risk gate. 
3. **Immutability and Auditability**: Interception allows the system to deterministically publish `TradeRejectedByRiskEvent` and `RiskBudgetExhausted` events to the `EventStore` before the command is ever processed by a handler.
4. **Separation of Concerns**: Broker plugins are simplified; their only job is to execute trades. The platform handles Observability (M6) and Risk (M7) via distinct decorators (`ObservableBus` and `RiskGuardedCommandBus`).

## Consequences
- Every `ExecuteTradeCommand` must have an associated `strategy_id` (or equivalent) that maps to a `RiskBudget`.
- `ExecuteTradeCommand` must include an `estimated_value` so the engine can check the required capacity before passing it to the plugin.
- The `RiskGuardedCommandBus` assumes the role of halting dispatch logic, returning `None` or raising an exception if a trade is rejected, ensuring the plugin is never invoked.
