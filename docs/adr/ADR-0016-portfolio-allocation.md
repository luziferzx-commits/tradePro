# ADR-0016: Portfolio Capital Allocation and Pipeline Refactoring

## Context

In Milestone 9C (M9C), we addressed the architectural need to formally separate "Capital Allocation" from "Risk Budgeting" and "Position Sizing". Prior to M9C, `PortfolioSnapshot` was manually mocked and injected into the sizing engine without systemic cash reservation guarantees. 

As GQOS handles multi-strategy execution, it requires a centralized Portfolio Manager to allocate sub-budgets to strategies, enforce buying power limits, and safely reserve capital while a trade is in transit.

## Decision 1: `PortfolioManager` and `StrategyAllocation`

We introduced a formal `PortfolioManager` that tracks `PortfolioState` and individual `StrategyAllocation` buckets.

* **Rationale**: Sizing algorithms answer "How many units?" based on a conceptual bucket of capital. By letting the `PortfolioManager` provide a localized `PortfolioSnapshot` per strategy, the Sizing Layer remains perfectly pure and isolated from multi-strategy cross-contamination.

## Decision 2: Contextual Stage Pipeline Refactoring

We refactored `TradingPipeline` to use a strongly typed `PipelineContext` instead of a dictionary. 

* **Rationale**: This guarantees that stages explicitly declare their structural dependencies (e.g., `PipelineContext.snapshot`). It provides compile-time safety and prevents loose dictionary-key errors. `PortfolioSnapshotStage` was introduced as the first stage to construct and inject this snapshot.

## Decision 3: Atomic `PortfolioReservationStage`

We introduced `PortfolioReservationStage` placed immediately after `RiskBudgetStage` and before `ExecutionStage`.

* **Rationale**: This guarantees that cash is only reserved if the trade has survived all risk limits, exposure checks, and circuit breakers. If the `ExecutionStage` subsequently fails (e.g. network timeout or synchronous broker rejection), it catches the exception and deterministically calls `release_cash()`, emitting a `CashReleasedEvent`.

## Decision 4: Flat Allocation Topology

For M9C, we explicitly restricted the topology to a flat `Portfolio -> Strategy` model.

* **Rationale**: This prevents premature complexity (hierarchical DAG allocations) while providing all the functional primitives needed for M9D (Multi-Strategy Allocation). 

## Status

Approved and implemented in M9C.
