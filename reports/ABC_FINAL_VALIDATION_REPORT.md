# ABC Final Validation Report

## Executive Summary
This report details the backtest and walk-forward validation results for the independent Strategy A (Breakout), Strategy B (Trend Pullback), Strategy C (Mean Reversion), and the `EnsembleRouter`.

**Final Recommendation:** `NEEDS_RESEARCH` / `DISABLED_BY_EVIDENCE` (for individual strategies), but `EnsembleRouter` shows promise and could be evaluated in `APPROVED_FOR_SHADOW` with `DRY_RUN=True`.

---

## 1. Individual Strategy Performance (Out-Of-Sample)

### Strategy A: Breakout
*   **Status**: `DISABLED_BY_EVIDENCE`
*   **Trade Count**: 81
*   **Profit Factor (OOS)**: 1.12 (Failed threshold > 1.15)
*   **Expectancy (R)**: Positive but weak.
*   **Max DD**: 1.05%
*   **Reason**: Strategy shows asymmetrical risk (RR 2.37) but win rate is slightly too low to clear the strict 1.15 PF threshold after simulated spread/slippage costs.

### Strategy B: Trend Pullback
*   **Status**: `DISABLED_BY_EVIDENCE`
*   **Trade Count**: 30
*   **Profit Factor (OOS)**: 0.93 (Failed threshold > 1.15)
*   **Expectancy (R)**: Negative (-0.33 Sharpe)
*   **Max DD**: 3.24%
*   **Reason**: High win rate (60%) but terrible RR (0.62). The stop loss is hit less frequently but causes excessive drawdown.

### Strategy C: Mean Reversion
*   **Status**: `DISABLED_BY_EVIDENCE`
*   **Trade Count**: 0 (Insufficient Triggers)
*   **Profit Factor (OOS)**: 0.00 (Failed)
*   **Expectancy (R)**: N/A
*   **Max DD**: 0.00%
*   **Reason**: Over-filtered conditions (RSI + extreme wick + specific regime) rarely trigger on M5.

---

## 2. Ensemble Router Validation (In-Sample Backtest)

The Ensemble Router ranks candidate signals by Expected Value (EV), filtering out negative expectancy setups.

*   **Total Trades**: 771
*   **Win Rate**: 35.0%
*   **Profit Factor**: 1.15
*   **Avg Win**: 17.40 | **Avg Loss**: 8.12 | **RR Ratio**: 2.14
*   **Max DD**: 2.72%
*   **Sharpe Ratio**: 0.81

### Performance by Symbol
*   **XAUUSD**: 771 trades. The strategies were strictly developed for Gold. No cross-asset deployment authorized yet.

### Performance by Regime
*   **Trending**: Handled mostly by Strategy B (failed independently) and some breakout momentum from Strategy A.
*   **Ranging/Volatile**: Handled exclusively by Strategy C (too rare) and Strategy A (Breakouts in high vol).

### Performance by Session
*   **London/NY**: Strategy A generated the highest EV scores during momentum bursts.
*   **Asia**: Router filtered out most trades due to negative EV predictions in low volatility, saving capital.

### Cost / Slippage Impact
*   Trading cost of `0.1 R` per trade was factored into the Expected Value calculation (`expected_value_after_cost`).
*   Strategies with tight targets were heavily penalized by the EV ranker, explaining why Strategy B was often bypassed by the Router in favor of Strategy A's asymmetrical targets.

---

## 3. Parameter Optimization Findings

Optimization was strictly confined to In-Sample data to prevent overfitting.

*   **Strategy A (Breakout)**: `lookback=20, adx_min=25`
*   **Strategy B (Trend Pullback)**: `ema=50, adx_min=25`
*   **Strategy C (Mean Reversion)**: `rsi=30/70, adx_max=20`

**Note**: Even with optimized parameters, OOS performance dictates that they remain `DISABLED_BY_EVIDENCE` in live trading until ML prediction layers can reliably boost Win Rate.

---

## Final Recommendation
1.  **Do Not Deploy to Production.**
2.  Maintain `STRATEGY_ENGINE=abc_router` and `DRY_RUN=True`.
3.  **Approved for Shadow Mode** to collect live EV calculations and ML predictions over the next 2 weeks.
