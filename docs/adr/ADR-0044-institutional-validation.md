# ADR-0044: Institutional Statistical Validation

## Context
With the introduction of the Alpha Factory in M25, GQOS gained the capability to automatically generate thousands of alpha strategy permutations. However, evaluating thousands of strategies introduces extreme Multiple Testing Bias. A strategy with a high Sharpe ratio might simply be a statistical anomaly rather than a robust edge. To elevate the platform to an **Institutional Alpha Discovery Platform**, we required rigorous statistical lie-detectors.

## Decision 1: Probability of Backtest Overfitting (PBO) via CPCV
We implemented Combinatorial Purged Cross Validation (CPCV) and the Probability of Backtest Overfitting (PBO) metric using Combinatorially Symmetric Cross Validation (CSCV).
* **Rationale**: Purged K-Fold is excellent for ML training, but to truly assess backtest overfitting, we need to generate thousands of simulated backtest paths. PBO mathematically calculates the probability that the strategy chosen as optimal *In-Sample* will perform below the median *Out-of-Sample*. A high PBO immediately flags an overfitted Alpha Factory configuration.

## Decision 2: Fractional Differentiation & AutoFD
Standard integer differencing ($d=1$) makes a financial time series stationary but destroys its memory (the core signal). We implemented Fixed-Window Truncated Fractional Differentiation ($0 < d < 1$) along with an `AutoFD` selector that uses the Augmented Dickey-Fuller (ADF) test to find the minimum $d$ required for stationarity.
* **Rationale**: We rejected Fast Fourier Transform (FFT) due to the high risk of look-ahead leakage in rolling implementations. The fixed-window approach guarantees chronological purity and auditability, which is mandatory for production.

## Decision 3: Path-Dependent Triple Barrier Method (TBM)
We moved away from fixed-horizon return predictions in favor of the path-dependent Triple Barrier Method (Upper Profit Taking, Lower Stop Loss, Vertical Time Expiration).
* **Rationale**: Real trading is path-dependent. An Alpha that correctly predicts a $5\%$ move over 10 days is useless if the asset drops $10\%$ on day 2 and hits a stop loss. TBM captures this reality. Furthermore, the `TripleBarrierMethod` now outputs meta-labels (holding time, barrier hit type) to serve as advanced ML features.

## Decision 4: False Discovery Rate (FDR) & Bootstrap Reality Checks
We implemented Benjamini-Hochberg FDR control alongside a centralized `BootstrapEngine` powering White's Reality Check and Hansen's Superior Predictive Ability (SPA).
* **Rationale**: Bonferroni (FWER) is too conservative for a factory evaluating thousands of signals. FDR is the industry standard for discovering real edge while mathematically capping the percentage of false positives. SPA provides a superior baseline over White's RC by dynamically re-centering poor performing models.

## Status
Approved and implemented in M26.
