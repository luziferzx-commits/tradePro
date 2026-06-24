# ADR-0045: Portfolio Management and Allocation

## Context
With the completion of M26, the GQOS Alpha Factory is capable of discovering and statistically validating dozens of Alphas. However, treating all valid Alphas identically and allocating capital statically creates catastrophic risk (e.g., highly correlated Alphas crashing simultaneously, or degraded Alphas continually losing money). To solve this, M27 introduces a dynamic Portfolio Management subsystem.

## Decision 1: Hierarchical Risk Parity (HRP) over Mean-Variance
We implemented HRP instead of traditional Mean-Variance optimization for correlation control.
* **Rationale**: Mean-Variance optimization requires inverting the covariance matrix, which is highly unstable and extremely sensitive to estimation errors out-of-sample. HRP utilizes machine learning (hierarchical clustering) to group Alphas into a tree structure based on correlation distance, allocating risk top-down. This provides significantly more robust out-of-sample diversification without matrix inversion.

## Decision 2: Fractional Kelly with Independent Approximation
We implemented the `CapitalAllocator` interface supporting `FractionalKellyAllocator`.
* **Rationale**: Full Kelly sizing is mathematically optimal for long-term growth but practically unusable due to extreme short-term drawdowns. We implemented Fractional Kelly (e.g., Half-Kelly) to smooth the equity curve. Furthermore, we calculate Kelly for each Alpha independently and scale them down. Since HRP has already orthogonalized the portfolio weights, the independent approximation provides computational stability compared to full Multivariate Kelly sizing.

## Decision 3: Alpha Lifecycle State Machine & Shadow Routing
We replaced binary Alpha states with a full lifecycle: `Candidate` $\rightarrow$ `Challenger` $\rightarrow$ `Champion` $\rightarrow$ `Watchlist` $\rightarrow$ `Retired` $\rightarrow$ `Graveyard`. This is integrated directly into the `ShadowRouter`.
* **Rationale**: New Alphas (Challengers) must prove themselves without risking live capital. The Shadow Router strictly allocates `0.0` capital to Challengers, executing their trades entirely in a shadow ledger. Only Champions receive live capital.

## Decision 4: Dynamic Alpha Health Score & Drift Integration
We implemented `AlphaHealthScore` to dynamically scale an Alpha's weight based on Rolling Sharpe, Max Drawdown, PBO, and most importantly, **Feature Drift** (from M14C).
* **Rationale**: Alphas decay. A static weight allocation ignores market regime shifts. By integrating Feature Drift directly into the Health Score, the portfolio manager autonomously shrinks the capital allocated to an Alpha the moment its underlying predictive features begin to drift from their training distribution, intercepting drawdowns before they fully materialize.

## Status
Approved and implemented in M27.
