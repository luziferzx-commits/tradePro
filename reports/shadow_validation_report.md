# Shadow Mode Validation Report

**Date:** 2026-06-25 01:00:54
**Verdict:** CAUTION

## 1. Overview
- Total Signals Processed: 1390
- Live Orders Sent: 0
- Dry-Run Orders Blocked: 196
- Total Risk Budget Consumed (Sum of all approved): 1.9048%

## 2. Scanner Performance
- Approved: 222
- Rejected: 1168
### Top Scanner Rejection Reasons
- 22x: Low model probability 0.22 < 0.55 | Expected R 0.00 <= 0 | Extreme volatility regime
- 21x: Low model probability 0.39 < 0.55
- 21x: Low model probability 0.47 < 0.55
- 20x: Low model probability 0.33 < 0.55
- 20x: Low model probability 0.28 < 0.55 | Expected R 0.00 <= 0

## 3. Portfolio Engine Performance
- Approved: 196
- Resized (Correlation/Risk): 11
- Rejected: 26
### Top Portfolio Rejection Reasons
- 6x: Min lot bump (0.01) causes risk breach: Exceeds max CRYPTO risk (2.05% > 2.00%)
- 5x: Exceeds max total risk (3.02% > 3.00%)
- 4x: Exceeds max total risk (3.05% > 3.00%)
- 3x: Min lot bump (0.01) causes risk breach: Exceeds max total risk (3.00% > 3.00%)
- 2x: Min lot bump (0.1) causes risk breach: Exceeds max total risk (3.02% > 3.00%)

## 4. Warnings & Safety
- Total Warnings Generated: 1390
- DD Guard Triggers: 0
- Journal Completeness: 100% (No missing critical fields)
