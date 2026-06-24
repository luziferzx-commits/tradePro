# B2 Meta Learning Research Report

## Objective
Identify which observer variables best predict trade outcomes (Win/Loss) without modifying the core trading logic. 

## Data Sources
- `results/context_preds.csv` (Baseline candidate probabilities and edge scores)
- `data/market_memory.json` (Contextual historical performance)
- *Note: `data/telemetry.db` was skipped due to insufficient rows in the current Shadow Validation phase.*

## Feature Importance Ranking
The following table shows the relative predictive power of each variable using a Random Forest Classifier (Gini Importance):

| Feature               |   Importance |
|:----------------------|-------------:|
| market_score          |    0.430555  |
| candidate_probability |    0.418408  |
| market_regime         |    0.0812292 |
| session               |    0.069808  |
| volatility_bucket     |    0         |
| direction             |    0         |
| memory_confidence     |    0         |
| memory_pf             |    0         |
| memory_matches        |    0         |

## Key Insights
1. **Memory Features vs Candidate Probability**: Look at where `candidate_probability` ranks compared to `memory_pf` or `market_score`. This tells us if historical context adds value over the raw ML prediction.
2. **Categorical Regimes**: Variables like `market_regime` and `session` might have lower raw Gini importance than continuous variables, but they are crucial for defining the context (Memory Key).
3. **Actionable Takeaway**: Do NOT build a new model yet. Use these findings to monitor Shadow Validation. If the top predictor diverges from expectation, that's where the system breaks.
