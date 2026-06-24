# ADR-0024: Portfolio Optimization Core & Solver Boundary

## Context

In M12A, GQOS required the foundational structures to support Portfolio Construction & Optimization. A major risk with optimization engines (like Mean-Variance or Risk Parity) is that they become heavily coupled to specific mathematical libraries (like `scipy.optimize` or `cvxopt`), making the core domain difficult to test, replay, and maintain. 

## Decision 1: Solver Dependency Boundary (`IOptimizer`)

We defined `IOptimizer` as an interface that completely abstracts the underlying mathematical solver. The core GQOS domain (M12A) remains 100% pure Python without any external dependencies.

* **Rationale**: This establishes a hard boundary. When we introduce `scipy.optimize` in M12B to handle complex quadratic programming (QP) solvers, it will exist solely as an adapter (e.g., `ScipyMeanVarianceOptimizer`) that implements `IOptimizer`. The core pipeline does not know or care that `scipy` is being used.

## Decision 2: Immutable Target State

The `IOptimizer` evaluates an `OptimizationProblem` and strictly outputs an immutable `TargetPortfolio` (a mapping of symbols to absolute target weights).

* **Rationale**: The Optimizer's only job is to answer "What is the theoretical ideal portfolio given these inputs?". It must *not* attempt to calculate trade deltas, generate orders, or execute rebalances. This completely separates **Optimization** from **Execution** (which will be handled in M14 Rebalance Engine).

## Decision 3: Deterministic Constraints

Constraints (`MaxWeightConstraint`, `SumToOneConstraint`, `SectorWeightConstraint`) are built as discrete classes fulfilling the `IConstraint` interface, completely separate from the Optimizer.

* **Rationale**: Some mathematical solvers struggle with complex constraints or silently breach them due to floating-point tolerances. By extracting Constraints as standalone validators, we can independently verify the `TargetPortfolio` output against the exact rules, ensuring the solver did not produce a mathematically "optimal" but practically illegal portfolio.

## Status

Approved and implemented in M12A.
