# Phase 4: Feature Kill List & Robustness Report

## 1. 3-Layer Feature Elimination (MDA & SHAP)
| Feature | MDA | S-Score | SHAP Consistency | Classification |
|---------|-----|---------|------------------|----------------|
| `reversal_score` | 0.0000 | 0.80 | 49.4% | **KEEP** |
| `session_score` | 0.0000 | 0.75 | 37.6% | **KEEP** |
| `atr` | 0.0000 | 0.83 | 57.2% | **KEEP** |
| `ema50_slope` | 0.0000 | 0.88 | 69.6% | **KEEP** |
| `rsi` | 0.0000 | 0.79 | 48.1% | **KEEP** |
| `macd` | 0.0000 | 0.85 | 62.2% | **KEEP** |
| `hour_utc` | 0.0000 | 0.85 | 63.7% | **KEEP** |
| `recent_high_20_distance` | 0.0000 | 0.82 | 55.4% | **KEEP** |
| `recent_low_20_distance` | 0.0000 | 0.82 | 55.9% | **KEEP** |
| `final_score` | 0.0000 | 0.60 | 0.0% | **WEAK_SIGNAL** |
| `trend_score` | 0.0000 | 0.65 | 13.7% | **WEAK_SIGNAL** |
| `breakout_score` | 0.0000 | 0.60 | 0.0% | **WEAK_SIGNAL** |
| `adx` | 0.0000 | 0.72 | 29.3% | **WEAK_SIGNAL** |
| `is_high_volatility` | 0.0000 | 0.65 | 12.2% | **WEAK_SIGNAL** |
| `is_buy` | 0.0000 | 0.60 | 0.0% | **WEAK_SIGNAL** |

## 2. Feature Decay Test
| Feature | Lag 10 Drop | Noise Flag |
|---------|-------------|------------|

## 3. Cross-Market Robustness (Core Features Only)
| Market | Tier | OOS PF | Status |
|--------|------|--------|--------|
| `XAUUSDm` | 1 | 0.00 | ❌ FAIL |
| `XAGUSDm` | 1 | 0.00 | ❌ FAIL |
| `EURUSDm` | 2 | 0.00 | ❌ FAIL |
| `GBPUSDm` | 2 | 0.00 | ❌ FAIL |
| `BTCUSDm` | 3 | 0.00 | ❌ FAIL |
| `US30m` | 3 | 0.00 | ❌ FAIL |

## Final Surviving Features
The following features survived all Hedge Fund-grade tests and will be used for Phase 5:
- `reversal_score`
- `session_score`
- `atr`
- `ema50_slope`
- `rsi`
- `macd`
- `hour_utc`
- `recent_high_20_distance`
- `recent_low_20_distance`