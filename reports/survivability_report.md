# Survivability & Risk of Ruin Report
Generated on: 2026-06-25 00:41:26

> [!WARNING]
> **SYNTHETIC DATA USED**
> No real trade history was found. This report uses a synthetic fallback dataset.
> The metrics below are theoretical. Please run on real trade history before live deployment.

## 1. System Metrics (Input)
- **Historical Trades Analyzed**: 500
- **Data Source**: SYNTHETIC_FALLBACK

## 2. Stress Test Results

### Base Case
- **Avg Expectancy**: -0.09R
- **Expected 95th Percentile Max Drawdown**: 66.00R
- **Probability of 10R Drawdown**: 99.94%
- **Probability of 20R Drawdown**: 91.48%
- **Probability of 30R Drawdown**: 68.83%
- **Probability of 50R Drawdown (Ruin)**: 23.24%
- **Probability of 10 Consecutive Losses**: 88.00%

### Slippage Shock (-0.1R)
- **Avg Expectancy**: -0.19R
- **Expected 95th Percentile Max Drawdown**: 88.50R
- **Probability of 10R Drawdown**: 100.00%
- **Probability of 20R Drawdown**: 99.07%
- **Probability of 30R Drawdown**: 93.72%
- **Probability of 50R Drawdown (Ruin)**: 63.89%
- **Probability of 10 Consecutive Losses**: 88.20%

### Severe Slippage Shock (-0.25R)
- **Avg Expectancy**: -0.34R
- **Expected 95th Percentile Max Drawdown**: 125.26R
- **Probability of 10R Drawdown**: 100.00%
- **Probability of 20R Drawdown**: 100.00%
- **Probability of 30R Drawdown**: 99.91%
- **Probability of 50R Drawdown (Ruin)**: 97.71%
- **Probability of 10 Consecutive Losses**: 89.70%

### Bad Regime Shock (-20% WR)
- **Avg Expectancy**: -0.29R
- **Expected 95th Percentile Max Drawdown**: 108.00R
- **Probability of 10R Drawdown**: 100.00%
- **Probability of 20R Drawdown**: 99.96%
- **Probability of 30R Drawdown**: 99.57%
- **Probability of 50R Drawdown (Ruin)**: 92.81%
- **Probability of 10 Consecutive Losses**: 99.00%

### Loss Streak Shock (+10 initial losses)
- **Avg Expectancy**: -0.11R
- **Expected 95th Percentile Max Drawdown**: 69.00R
- **Probability of 10R Drawdown**: 99.98%
- **Probability of 20R Drawdown**: 93.66%
- **Probability of 30R Drawdown**: 74.85%
- **Probability of 50R Drawdown (Ruin)**: 28.60%
- **Probability of 10 Consecutive Losses**: 90.80%

### Worst Regime Bootstrap (Bottom 40%)
- **Avg Expectancy**: -1.00R
- **Expected 95th Percentile Max Drawdown**: 250.00R
- **Probability of 10R Drawdown**: 100.00%
- **Probability of 20R Drawdown**: 100.00%
- **Probability of 30R Drawdown**: 100.00%
- **Probability of 50R Drawdown (Ruin)**: 100.00%
- **Probability of 10 Consecutive Losses**: 100.00%

## 3. Verdict & Recommendations
**SYSTEM VERDICT**: ❌ FAIL (Base case failed minimum requirements)

- **Recommended Risk Per Trade**: 0.30% (Targeting <20% Account Drawdown on Base Case)
- **Capital Suitability ($500 balance)**: 
  - Risking 1% per trade = $5 risk. Max Expected DD = $330.00 (66.0% of balance).
  - **Survival Probability**: Poor (High chance of margin call)
