# ADR-0025: Optimization Engines & Solver Gate

## Context

In M12B, GQOS introduced real mathematical solvers (`scipy.optimize`) to resolve Portfolio Optimization problems. Given that `scipy` is a massive numerical dependency, integrating it safely without corrupting the pure domain model was a primary architectural concern. Additionally, QP solvers frequently struggle with ill-conditioned matrices or floating-point limits, requiring strict safety constraints.

## Decision 1: Scipy Adapter Pattern

We implemented `ScipyMeanVarianceOptimizer` and `ScipyRiskParityOptimizer` exclusively as adapters inheriting the `IOptimizer` interface. The `numpy` and `scipy` imports occur entirely within `gqos.portfolio.optimization.engines` and never leak into the domain models (`models.py`, `interfaces.py`, `constraints.py`).

* **Rationale**: If we later replace `scipy` with `cvxopt` or an external vendor API, the entire GQOS accounting, simulation, and execution pipeline remains utterly unchanged.

## Decision 2: Dual Constraint Mapping & Post-Validation

When the `IOptimizer` receives `IConstraint` definitions, it maps them into native SciPy boundaries and inequality functions so the solver has the mathematical "fences" to guide convergence. However, before returning the result, the optimizer *must* pass the final weights through the standalone `AllocationValidator`.

* **Rationale**: SciPy occasionally reports "success" but violates constraints by $10^{-5}$ due to floating-point truncation. By explicitly testing the output against the pure Python `AllocationValidator`, we guarantee that if the TargetPortfolio reaches the Execution layer, it is strictly and legally compliant.

## Decision 3: Automatic PSD Regularization

If the provided Covariance Matrix is non-Positive Semi-Definite (PSD) or singular, the engine automatically regularizes it via a Ridge penalty (adding a microscopic $\epsilon$ to the diagonal).

* **Rationale**: Historical returns of highly correlated assets (or a timeline shorter than the asset count) produce singular matrices that crash optimizers. Auto-regularization ensures the automated pipeline continues running reliably without human intervention.

## Status

Approved and implemented in M12B.
