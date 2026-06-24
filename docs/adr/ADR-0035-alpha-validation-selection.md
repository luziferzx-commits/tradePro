# ADR-0035: Alpha Validation and Selection

## Context

In M17, the goal was to separate robust, out-of-sample quantitative edge from overfitted noise. With the Alpha Library established in M16, we needed a rigorous statistical gauntlet to evaluate Information Coefficient (IC), handle Cross-Model Correlation, and execute Champion/Challenger ranking without falling victim to lookahead bias or over-optimization.

## Decision 1: Execution-Lagged Forward Returns (Anti-Lookahead)

We calculate Forward Returns explicitly using the `open_to_close` or `close_to_close_lag1` method in `AlphaValidationMetrics.generate_forward_returns`. 

* **Rationale**: A forecast generated at the end of bar $t$ (using `close[t]`) cannot physically be executed at `close[t]`. Standard retail backtests often calculate return as `(close[t+1] - close[t]) / close[t]`, which introduces massive lookahead bias. By forcing the return to be `(close[t+1] - open[t+1]) / open[t+1]`, we mathematically simulate the delay of routing market-on-open orders, guaranteeing that the IC represents achievable live trading performance.

## Decision 2: Alpha Selection Policy (Rejection over Orthogonalization)

In the `ChampionChallengerFramework`, when a new candidate Alpha exhibits a high correlation (e.g., > 0.7) with an existing Champion, the default action is to **Reject** the Challenger. 

* **Rationale**: While `AlphaMatrix` provides a mathematical Gram-Schmidt `orthogonalize` method, applying it automatically to highly correlated signals often results in overfitting the residual noise. We prioritize organically uncorrelated edge. Orthogonalization is strictly an optional, explicit override for special hedge cases. 

## Decision 3: Deterministic Objective Function

Alpha Ranking inside the `WalkForwardRanker` is driven by a static objective function: 
$Objective = (Rank IC \times 0.5) + (\min(Stability, 2.0) \times 0.15) - (\min(Turnover, 0.5) \times 0.4)$

* **Rationale**: We must balance predictive power (Rank IC) with the confidence of that power over time (Stability) and the physical cost of executing the signal (Turnover Penalty). This specific formulation prevents high-turnover noise models from dominating the ensemble.

## Status

Approved and implemented in M17.
