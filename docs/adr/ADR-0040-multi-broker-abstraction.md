# ADR-0040: Multi-Broker Abstraction & Translation

## Context

To transition GQOS from a simulated platform into a live trading system interacting with real capital (M22), it must be capable of executing orders on external exchanges (Binance, Interactive Brokers, etc.). However, binding the core OMS and Risk logic directly to Binance APIs would destroy the system's modularity and lock the architecture to a single vendor. Furthermore, exchanges have strict rules regarding price ticks and lot sizes that would pollute the mathematical purity of the internal Risk Engine.

## Decision 1: IBrokerAdapter Interface

We introduced the `IBrokerAdapter` as an impenetrable abstraction layer in `gqos/live/interfaces.py`.

* **Rationale**: The core `LiveTradingEngine`, `OMS`, and `AccountingEngine` must never import `binance` or `ibapi`. The core engine calls `submit_order(symbol, direction, quantity, price)` and the Adapter handles the network transport, payload formatting, and authentication. We use an `AdapterFactory` to dynamically inject the chosen adapter based on environment variables.

## Decision 2: Status Normalization Boundary

Each exchange defines order states differently. For example, Binance uses `PARTIALLY_FILLED` and `CANCELED`, while IBKR uses `Submitted` and `Cancelled`. 

* **Rationale**: The `IBrokerAdapter` is solely responsible for mapping these external vendor strings into our native `OrderStatus` Enum (`PARTIAL`, `CANCELLED`). This guarantees that the core GQOS OMS only ever processes standardized native state transitions.

## Decision 3: Adapter-Level Precision Adjustment

The Risk Engine operates in high-precision `Decimal` mathematics. However, Binance requires orders to conform exactly to `LOT_SIZE` (quantity stepping) and `PRICE_FILTER` (tick stepping).

* **Rationale**: The Risk Engine should not care about exchange-specific ticks. The `IBrokerAdapter` intercepts the incoming raw order, applies a floor-rounding mathematical adjustment based on the exchange's rules, and emits an `OrderAdjustedEvent` to the Event Bus for auditability. If the quantity rounds to zero, the Adapter rejects the order immediately without hitting the network.

## Decision 4: Testnet-First Approach

For the initial Binance implementation, we hardcoded the endpoints to `testnet.binance.vision`.

* **Rationale**: This guarantees that during the initial Multi-Broker architectural rollout, no real capital can be inadvertently risked. Real endpoints will only be introduced once the Testnet pipeline is fully validated.

## Status

Approved and implemented in M22.
