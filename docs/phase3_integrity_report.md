# Phase 3 Integrity Report

## CPCV Validation Parameters
- **Embargo Size**: 200 candles
- **Purge Size**: 10 candles
- **Number of Paths**: 15 (6 choose 2)
- **Strategy Grid Size**: 20 configs

## Overfitting Analytics (PBO)
- **PBO Score**: 80.00%
- **Average OOS Trades**: 252.9
- **Status**: INVALID (Trades < 300)

## Most Stable Strategy Analysis
The model selection mechanism prioritized the lowest variance across all 15 OOS paths.
- **Config**: `{'max_depth': 2, 'learning_rate': 0.01, 'n_estimators': 100, 'subsample': 0.9}`
- **Mean OOS PF**: 0.00
- **OOS PF Variance**: 0.0000

### Monte Carlo Block Bootstrapping
- **5th Percentile PF (Worst)**: N/A
- **50th Percentile PF (Median)**: N/A
