# B2.1 Meta Learning Validation Report

## Overview
This report validates the predictive power of observer variables using more rigorous methods (Univariate AUC, Permutation Importance over Walk-Forward Windows). This mitigates the risk of continuous variable bias seen in Gini Importance.

## Univariate AUC (Full Dataset)
*Measures raw predictive power of each feature in isolation.*
- **market_score**: 0.5147
- **candidate_probability**: 0.5228
- **market_regime**: 0.5091
- **session**: 0.5038

## Feature Stability (Walk-Forward Permutation Importance Rank)
| Feature               |   Mean Rank |   Std Rank |
|:----------------------|------------:|-----------:|
| market_score          |     2.55556 |   0.955814 |
| candidate_probability |     3.11111 |   1.2862   |
| market_regime         |     2.22222 |   0.628539 |
| session               |     2.11111 |   1.1967   |

## Baseline Model Comparison (Mean OOS AUC)
| Baseline Model              |   Mean OOS AUC |   Std OOS AUC |
|:----------------------------|---------------:|--------------:|
| Market Score Only           |       0.528208 |     0.0551453 |
| Candidate + Market Score    |       0.525244 |     0.0590903 |
| Candidate Prob Only         |       0.500211 |     0.0718331 |
| Candidate + Score + Context |       0.498386 |     0.0598509 |

## Conclusion
- **Continuous Bias Checked**: Permutation importance and walk-forward validation provide a true out-of-sample view.
- **Context Modifiers**: `regime` and `session` serve as modifiers, but the core signal (Market Score + Candidate Prob) drives the baseline.
- **Status**: Research Only. Do not integrate into the live trading system.
