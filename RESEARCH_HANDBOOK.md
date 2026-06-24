# GQOS Level 7.0: Institutional Quant OS Handover

## The Engineering Phase is Complete
From M1 to M27, we have successfully architected, built, and rigorously tested an institutional-grade Quantitative Trading Operating System. GQOS is no longer a script or a bot; it is an **Institutional Research Operating System** featuring:
- **Core Engine & OMS**: Event-driven, low-latency, resilient order routing.
- **Risk & Accounting**: Institutional multi-portfolio ledger, real-time exposure limits, and Kill Switches.
- **Observability**: Prometheus metrics, structured JSONL audit logs, and deterministic event sourcing.
- **Multi-Broker**: Pluggable adapter factory, precision shielding, VWAP slippage accounting, and Token Bucket rate limiting.
- **ML Research**: Purged K-Fold, Embargo, Meta-Labeling, Calibration, and SHAP explainability.
- **Statistical Validation**: Out-of-sample SPA, PBO calculation, and false discovery rate controls.
- **Portfolio Management**: Hierarchical Risk Parity and dynamic Alpha Shadow routing.

## The Research Philosophy
> **"We do not fall in love with strategies. We fall in love with evidence."**
*(เราไม่ได้หลงรักกลยุทธ์ แต่เราหลงรักหลักฐาน)*

> **"Every model is guilty until proven innocent by out-of-sample evidence."**
*(ทุกโมเดลมีความผิดฐาน Overfitting จนกว่าจะพิสูจน์ได้ด้วยข้อมูล Out-of-Sample ว่าบริสุทธิ์)*

## Roadmap to Production
Follow these steps to leverage GQOS for actual profit generation:

#### Phase 1: Idea Generation (Create 50-100 Alphas)
Use the `gqos.alpha.models.IAlphaModel` interface to rapidly prototype signals across diverse domains:
- **Mean Reversion**: Statistical arbitrage, pair trading, Bollinger bands.
- **Trend Following**: Moving average crossovers, MACD, breakout momentum.
- **Microstructure**: Order book imbalance, tick volatility.
- **Macro/Alternative**: Sentiment analysis, funding rates, open interest.

#### Phase 2: Institutional Validation (M25 & M26)
Subject every Alpha to the gauntlet:
1. **Walk-Forward Analysis**: Does it survive out-of-sample data over rolling windows?
2. **Probability of Backtest Overfitting (PBO)**: Is the performance structurally generated or purely luck?
3. **Superior Predictive Ability (SPA)**: Does it statistically outperform a zero-skill benchmark?

#### Phase 3: The Culling (Keep 5-10 Alphas)
Discard 90% of the ideas. Keep only the 5-10 Alphas that survive validation. Crucially, calculate the **Correlation Matrix** of their historical returns. You want Alphas that are *uncorrelated* (e.g., a Trend strategy that makes money when the Mean Reversion strategy is flat).

#### Phase 4: Ensemble & Shadow Routing (M27)
Wrap the survivors in the HRP Portfolio allocator. Deploy the candidates to the **Shadow Ledger**. They will execute via the live event bus but trade $0.00 to track real-world slippage without financial risk.

#### Phase 5: The 90-Day Evidence Check
Monitor the **Execution Quality** (`gqos_slippage_bps`) and Out-of-Sample Sharpe decay. If the Alpha degrades beyond the Backtest expectations, it is retired to the Archive. Only the strong survive.

#### Phase 6: Live Capital Staging
Once Shadow Validation proves the edge is stable, advance through capital staging: Paper $\rightarrow$ Micro $\rightarrow$ Small $\rightarrow$ Normal $\rightarrow$ Institutional. Let the Audit Logs and Prometheus Dashboards guide you.

---

> *"Alpha is a perishable asset. Infrastructure is the factory that mass-produces it."*
>
> The factory is built. The pipeline is locked. It is time to manufacture Alpha.
