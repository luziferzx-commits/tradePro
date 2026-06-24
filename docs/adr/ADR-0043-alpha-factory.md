# ADR-0043: Alpha Factory & Automated Tournament Pipeline

## Context

After establishing a rigorous Machine Learning and Validation boundary (M24), we recognized that creating strategies by hand is fundamentally inefficient and prone to human bias. To transform GQOS into a "Quantitative Research Factory" (M25), we needed a mechanism to procedurally generate, constrain, evaluate, and rank thousands of Alpha permutations autonomously without succumbing to Multiple Testing Overfitting.

## Decision 1: Template-Based Strategy Generation

We implemented `StrategyGenerator` to use a "Template + Parameter Grid" approach rather than unconstrained brute-force combinatorial logic.

* **Rationale**: Pure brute-force approaches often generate nonsensical "spaghetti logic" that fits the noise rather than the signal. By binding permutations to a core mathematical template (e.g., Mean Reversion, Cross-Sectional Momentum), we guarantee that every generated Alpha retains a foundation of economic intuition. Every generated `TemplateAlpha` calculates a deterministic `alpha_id` hash combining its template and parameter footprint.

## Decision 2: Constraint Engine Pre-Screening

Before any backtest is run, generated Alphas are passed through a `ConstraintEngine`.

* **Rationale**: Simulating 10,000 Alphas is computationally expensive. Many generated parameters will inherently violate physical market realities. The Constraint Engine rejects strategies with extreme turnover (which would be destroyed by slippage) or target sizes beyond the symbol's liquidity, pruning the search space rapidly.

## Decision 3: Deflated Sharpe Ratio (DSR) Ranking

In the Tournament phase, Alphas are ranked primarily by the **Deflated Sharpe Ratio (DSR)** rather than the standard Out-of-Sample Sharpe.

* **Rationale**: When you generate and test 10,000 strategies, the probability of finding a high Sharpe Ratio purely by random chance approaches 100% (Selection Bias / Multiple Testing). DSR mathematically adjusts the observed Sharpe Ratio downwards based on the variance of all trials and the number of permutations attempted. It provides the true probability that the strategy's edge is statistically significant.

## Decision 4: Safe Auto-Promotion

The Tournament concludes by registering the Top N uncorrelated winners into the `ChampionChallengerRegistry`.

* **Rationale**: An Alpha Factory should never deploy untested logic directly to live capital. The winners are stored as *Challengers*. They must subsequently survive strict Event-Driven Backtesting (M15), Paper Trading shadow periods, and manual Quant review before being promoted to Live Champions.

## Status

Approved and implemented in M25.
