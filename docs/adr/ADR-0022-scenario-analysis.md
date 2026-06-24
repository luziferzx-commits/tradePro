# ADR-0022: Scenario Analysis Architecture

## Context

In M11B, GQOS needed the capability to perform "What If" Stress Testing and Scenario Analysis. The system needed to shock the current portfolio positions against both historical crashes (e.g., 2008 Financial Crisis) and hypothetical scenarios (e.g., "Tech drops 20%").

## Decision 1: Pure Function Engine

The `ScenarioEngine` is designed as a strict Pure Function. It accepts the `positions`, a `scenario` definition, and a `security_master`, returning an immutable `ScenarioResult`. 

* **Rationale**: Maintains perfect determinism and replayability without mutating the core `AccountingState`.

## Decision 2: Shock Resolution Priority

Shocks defined in a Scenario are resolved in a strict priority order:
1. **Symbol-Specific Shock** (Highest)
2. **Sector-Level Shock**
3. **Global Default Shock** (Lowest)

* **Rationale**: This allows risk managers to apply broad market assumptions (e.g., "The whole market drops 10%") while explicitly overriding specific sectors or assets that have known idiosyncratic vulnerabilities (e.g., "But TSLA drops 30%").

## Decision 3: Scenario Composition (SUM Policy)

When a `CompositeScenario` combines multiple scenarios, the shocks are strictly summed together for overlapping entities. 
* **Rationale**: A `SUM` policy ensures deterministic accumulation without introducing non-linear interaction complexities (like Correlation or Copulas), which are deferred to M11C (Factor Analytics).

## Decision 4: Shock Unit Standardization

All shocks within the system are defined as explicit `Decimal` percentages where negative indicates a price drop (e.g., `-0.20` means a `-20%` reduction in price).

* **Rationale**: Prevents misinterpretation of absolute values vs relative drops.

## Status

Approved and implemented in M11B.
