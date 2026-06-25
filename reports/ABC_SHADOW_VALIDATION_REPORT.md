# ABC Strategy Shadow Validation Report

*Generated on: 2026-06-25 09:37:36*

## Executive Summary
This report summarizes the performance of the `EnsembleRouter` running in Shadow Mode (`DRY_RUN=True`).
**Target Duration:** Minimum 5 trading days.

**Final Recommendation:** `CONTINUE_SHADOW` (Insufficient data collected yet. Run for 5-10 days first).

---

## 1. Overall Shadow Metrics
*   **Total Signals Scanned**: 0
*   **Trades Approved by Router**: 0
*   **Trades Rejected by Router**: 0
*   **Live Order Violations**: 0 ✅ (Must be 0)

### Rejection Reason Breakdown
*   *Negative Expected Value (EV <= 0)*: 0
*   *Low Confidence Score*: 0
*   *Disabled by Evidence*: 0

---

## 2. Performance Analysis (Simulated)
*   **Simulated PnL**: $0.00
*   **Simulated Profit Factor**: 0.00 (Target >= 1.15)
*   **Expectancy (R)**: 0.00
*   **Win Rate**: 0.0%
*   **Average RR**: 0.00
*   **Max Drawdown**: 0.00%

### Strategy Selection Distribution
*   **Strategy A (Breakout)**: 0%
*   **Strategy B (Trend Pullback)**: 0%
*   **Strategy C (Mean Reversion)**: 0%

---

## 3. Performance by Category

### By Symbol
*   **XAUUSD**: 0 trades, 0.00 PF

### By Session
*   **Asia**: 0 trades
*   **London**: 0 trades
*   **NY**: 0 trades

### By Regime
*   **Trending**: 0 trades
*   **Ranging**: 0 trades
*   **High Volatility**: 0 trades

### Cost / Slippage Impact
*   **Avg Slippage Simulated**: 0.0 pips
*   **Total Spread Cost**: $0.00

---

## 4. Strategy Health Guard
*   *Are any strategies operating below PF 1.0?* **No data**
*   *Was the kill-switch triggered?* **No**
