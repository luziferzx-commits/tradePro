# ADR-0042: Financial Machine Learning Architecture

## Context

After stabilizing the GQOS execution infrastructure (M22.5), the platform is ready to host Machine Learning Alphas (M24). However, standard Machine Learning pipelines (e.g., standard K-Fold CV, standalone directional models) are highly prone to data leakage when applied to non-stationary, auto-correlated financial time series. We needed an institutional-grade ML architecture designed specifically for the domain.

## Decision 1: Purged K-Fold & Embargo over Standard CV

We explicitly prohibited the use of standard K-Fold Cross Validation. We implemented `PurgedKFold` in `gqos/research/ml/validation.py`.

* **Rationale**: In financial data, observation at time $t$ is highly correlated with time $t-1$ and $t+1$. Standard CV randomly assigns overlapping points to Train and Test sets, allowing the model to "memorize" the overlap and vastly overstating out-of-sample accuracy. `PurgedKFold` explicitly drops (purges) training data that overlaps with the testing boundaries and enforces a forward-looking gap (Embargo) to sever the serial correlation.

## Decision 2: Meta-Labeling Wrapper

Instead of having a single ML model predict Direction, Size, and Confidence, we separated the concerns using `MetaLabeledAlpha`.

* **Rationale**: We use a primary Alpha (e.g., a simple statistical mean-reversion) to dictate purely the *direction* (Buy/Sell) of the trade. The secondary ML model is trained exclusively on the binary outcome (Profit/Loss) of the primary model's historical trades to predict the *probability of success*. The Meta ML Model determines *size* and *confidence* but is programmatically prohibited from overriding the *direction*. This prevents black-box directional guessing.

## Decision 3: MDA over Single Feature Importance

For Feature Importance during the research phase, we implemented Mean Decrease Accuracy (MDA) coupled with Purged CV.

* **Rationale**: Standard Single Feature Importance (SFI) tests features in isolation, ignoring interaction effects. In-built tree importances (like Gini) are biased towards continuous features and overfit heavily. MDA, calculated on the *out-of-sample* Purged CV folds, measures the actual drop in predictive power when a feature is permuted, offering the most honest assessment of feature robustness.

## Decision 4: SHAP for Explanations

We integrated `SHAPExplainer` into the forecast generation pipeline.

* **Rationale**: Institutional capital cannot be deployed on "Black Box" logic. If the Meta Model predicts an 85% probability of success for a trade, the Risk Engine needs to know *why*. SHAP values distribute the prediction across the features, allowing us to log exact localized explanations into the `ForecastResult`'s `ExplanationStore` for every single trade.

## Status

Approved and implemented in M24.
