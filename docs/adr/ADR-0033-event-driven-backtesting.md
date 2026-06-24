# ADR-0033: Event-Driven Backtesting Parity

## Context

In M15, GQOS needed a mechanism to simulate the historical performance of Alpha forecasts (from M14). The industry standard for initial research is often a fast, vectorized backtester (e.g., multiplying a `score` vector by a `returns` vector). However, vectorized backtesting famously ignores path-dependency, margin limits, fractional slippage, and exact order-routing mechanics.

## Decision: Event-Driven Parity

We chose to implement the `EventDrivenBacktester` which physically instantiates and wires together the *exact same* Execution, Risk, and Accounting modules (M1-M11) that are used in Live Trading. 

* **Rationale**: The core philosophy of GQOS is "Institutional Standard". If a strategy looks profitable in research but fails in live execution due to margin constraints or slippage, it is useless. By forcing the Backtester to act simply as a "Simulation Clock"—iterating through time and emitting `MarketEvent` and `ForecastEvent` into the `EventBus`—we guarantee that the `AccountingEngine` and `PortfolioManager` process the mock `FillEvents` exactly as they would process a live Fill from a broker.

## Decision: Minimum Viable Translation

Rather than building a highly complex `RebalanceEngine` in M15, the Backtester currently acts as a simple inline translator. It converts a `TargetPortfolioEvent` directly into `ExecuteTradeCommand`s by calculating the `quantity_diff` against the `AccountingEngine`'s current open positions.

* **Rationale**: This limits the scope of M15 to pure execution simulation. Advanced multi-asset rebalancing algorithms, sector constraints, and portfolio-level optimizations are handled upstream in the `PortfolioOptimization` engine (M12).

## Decision: Friction Models

We implemented `FixedBpsSlippage` and `FixedCommission` directly into a `MockExecutionHandler`.

* **Rationale**: By intercepting `ExecuteTradeCommand` before it hits the `AccountingEngine`, we can dynamically deduct liquidity costs (slippage) from the executed price, and emit a `FeeChargedEvent`. This guarantees that the `equity_curve` generated during backtesting accurately reflects real-world trading friction.

## Status

Approved and implemented in M15.
