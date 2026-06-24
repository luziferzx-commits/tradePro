# ADR-0037: Live Trading Platform Architecture

## Context

Milestone 19 transitions GQOS from a Paper Trading simulator to a Pre-Production Live Trading Platform. Moving to live execution introduces immense risks: API disconnects, partial fills, sudden system crashes, and out-of-sync ledgers. M19 establishes the safety, recovery, and order lifecycle mechanisms necessary to protect real capital.

## Decision 1: Order Lifecycle Management (OMS)

We implemented an `OrderManagementSystem` that tracks the full state machine of a live order: `NEW` $\rightarrow$ `ACK` $\rightarrow$ `PARTIAL` $\rightarrow$ `FILLED` (or `CANCELLED`/`REJECTED`/`EXPIRED`).

* **Rationale**: In paper trading, an order is either queued or filled. In live trading, an order might sit on the exchange book partially filled for hours. By broadcasting `OrderUpdateEvent` and emitting `TradeExecutedEvent` incrementally upon partial fills, the `AccountingEngine` accurately reflects real-time exposure. If we waited for a complete fill to update accounting, the Risk Gateway would evaluate against stale data, potentially allowing a breach of limits.

## Decision 2: Broker Truth Override & Startup Reconciliation

If the trading engine crashes and restarts, the `LiveTradingEngine` first restores the internal `AccountingEngine` state from a disk snapshot (`LedgerSnapshotService`). It then immediately queries the Broker Adapter for the actual positions. If there is a mismatch (e.g., an order filled while GQOS was offline), **Broker Truth Overrides Local State**.

* **Rationale**: The exchange holds the ultimate truth of our capital. If we assume the local ledger is correct despite a discrepancy, we could double-spend capital or hold unhedged risk. By emitting a `ReconciliationFillEvent` and blocking all trading until the mismatch is accounted for, we guarantee absolute ledger integrity.

## Decision 3: Global Safety & Kill Switches

We introduced two primary safety mechanisms:
1. **Global Kill Switch**: When triggered, it permanently blocks all new orders from being created and actively attempts to cancel all currently open orders on the exchange.
2. **Heartbeat Monitor**: The Broker Adapter continuously emits a `HeartbeatEvent`. If the engine misses this event beyond a timeout, it automatically triggers the Kill Switch.

* **Rationale**: Algorithms cannot trade blindly. If the websocket drops or the API is unresponsive, any generated signals are executing against stale data. The Heartbeat timeout ensures that a severed connection immediately halts risk-taking, rather than queuing up a massive backlog of "blind" orders.

## Status

Approved and implemented in M19.
