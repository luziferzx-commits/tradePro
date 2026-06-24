# ADR-0014: Kelly Criterion and Stage-Based Trading Pipeline

## Context

As part of Milestone 9A (M9A) of the GQOS Quant Decision Platform, we aimed to introduce **Kelly Criterion** for position sizing, transitioning from simple fixed-fraction risk models. Additionally, the execution flow relied heavily on a nested decorator pattern (`RiskGuardedCommandBus` wrapping `PositionSizingPipeline`), which proved increasingly difficult to extend and maintain as more quantitative rules and layers were added.

## Decision 1: StrategyMetrics Carried in Commands

We decided that for M9A, `KellyPolicy` will receive `Win Rate (W)` and `Win/Loss Ratio (R)` via a `StrategyMetrics` object embedded inside `SizePositionCommand`.

**Rationale:**
*   **Statelessness:** The Sizing Engine and its Policies remain pure functions.
*   **Replay Fidelity:** Exact inputs to the Kelly formula are captured in the event log (`PositionSizedEvent.sizing_reason`), allowing 100% deterministic replays without relying on external metrics registries mutating over time.
*   *Note for M9+:* Although the metrics are currently "mocked" as static inputs during tests, future milestones will source verified live metrics before dispatching the command. The ADR explicitly dictates that the metrics source remains an input, rather than letting the Kelly Policy fetch it from a registry directly.

## Decision 2: Fractional Kelly with Max Caps

`KellyPolicy` defaults to "Full Kelly" (multiplier 1.0) but supports Fractional Kelly (e.g., `0.5` for Half-Kelly). It also natively supports a `max_kelly_fraction` to cap runaway position sizing.

**Rationale:**
*   Full Kelly is known to produce extreme volatility and risk of ruin if assumptions about W and R are overly optimistic.
*   Half-Kelly or Quarter-Kelly provides superior risk-adjusted returns with drastically reduced drawdowns.
*   Any negative Kelly output immediately halts sizing and emits a `SizingFailedEvent`.

## Decision 3: Stage-Based Trading Pipeline

We introduced `TradingPipeline` with sequential `IPipelineStage` implementations to replace the deeply nested decorator pattern.

**Rationale:**
*   **Flattened Architecture:** Stages (`SizingStage -> CircuitBreakerStage -> ExposureStage -> RiskBudgetStage -> ExecutionStage`) process sequentially.
*   **StageResult Output:** `process()` returns a `StageResult` instead of a boolean. This enables the stage to mutate envelopes, carry forward emitted events, or halt the pipeline with specific reasons (`continue_pipeline`, `envelope`, `reason`, `emitted_events`).
*   **Equivalence Tested:** The new `TradingPipeline` underwent 1-to-1 deterministic replay equivalence testing against the old `RiskGuardedCommandBus`. Both pipelines produced exactly the same resulting commands and event streams for equivalent scenarios.

## Status

Approved for Implementation in M9A.
