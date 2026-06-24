# ADR-0017: Event-Sourced Accounting Ledger

## Context

In Milestone 10A (M10A), GQOS introduces the Accounting Layer. The Accounting Engine sits immediately downstream of the Execution Layer. It processes `TradeExecutedEvent`s to construct deterministically reproducible ledgers for positions, cash, and realized PnL. This is a critical component before any Portfolio Optimizers, Tax accounting, or Kelly models can function over live data.

## Decision 1: Event-Sourced State vs Double-Entry Bookkeeping

We chose an **Event-Sourced State Model** for the `AccountingEngine` over a strict traditional Double-Entry Ledger (Credit/Debit entries per action).

* **Rationale**: The engine calculates all changes to cash, fees, and positions explicitly, and publishes standard domain events (`PositionOpenedEvent`, `PositionAdjustedEvent`, `PositionClosedEvent`, `FeeChargedEvent`, `RealizedPnLEmittedEvent`). The exact State of any Portfolio or Strategy can be reconstructed by simply replaying these events from the Event Store. This avoids the excessive structural rigidity of pure Double-Entry systems while maintaining 100% deterministic reproducibility. 

## Decision 2: Accounting vs Portfolio Synchronization

The `AccountingEngine` and `PortfolioManager` are kept decoupled via an Event-Driven boundary. 

* **Rationale**: The `AccountingEngine` calculates Realized PnL when a position is closed and emits `RealizedPnLEmittedEvent`. The `PortfolioManager` independently listens to this event to update `total_equity` and `allocated_capital`. This unidirectional data flow preserves the Separation of Concerns, ensuring that the accounting component remains ignorant of allocation mechanisms.

## Decision 3: Average Cost Basis

For M10A, we enforce the **Average Cost** methodology for resolving partial closes. 

* **Rationale**: This is the industry standard for simplified continuous trading. `FIFO`/`LIFO` implementations are deferred as optional future accounting policies to prevent premature complexity in the foundational layer.

## Decision 4: Fee and Slippage Extraction

Fees and slippage are not hardcoded into the `TradeExecutedEvent` by the execution plugins. Instead, the `AccountingEngine` employs an injected `IFeeModel`.

* **Rationale**: This guarantees that the Execution layer's single responsibility remains "What occurred?" while the Accounting layer answers "What does it cost?". This enables strategies or environments to use identical execution events but different fee schedules (e.g., Simulated vs Live broker).

## Status

Approved and implemented in M10A.
