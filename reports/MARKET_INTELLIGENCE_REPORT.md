# Market Intelligence Report
*Generated on: 2026-06-25 10:16:41*

> [!WARNING]
> **RESEARCH_EXECUTION_MODEL = candle_close_fill**
> `spread_model = SIMULATED_DYNAMIC_ATR_BASED`.

## 1. Engine Benchmark
|    | engine   |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:---------|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Legacy   |      616 | 1.09 |    0.12 |         -1 |     44.81 |     1.5 |  186.75 |            1.5 |             0 |

## 2. Time Robustness (Yearly Impact)
|    |   year |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|-------:|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 |   2026 |      616 | 1.09 |    0.12 |         -1 |     44.81 |     1.5 |  186.75 |            1.5 |             0 |

## 3. Stability Test (Progressive Chunks)
No pattern reached 30 trades for stability testing.

## 4. Market DNA Profiles
### XAUUSD
- **Best Session**: LONDON
- **Core Strategy**: London Breakout
- **Optimal Volatility**: High
### EURUSD
- **Best Session**: LONDON_NY_OVERLAP
- **Core Strategy**: NY Breakout
- **Optimal Volatility**: Extreme

## 5. Symbol × Session Profit Factor Heatmap
| symbol   |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:---------|-------:|---------:|--------------------:|-----------:|--------------:|
| EURUSD   |   1.79 |     1.16 |                1.63 |       0.89 |          1.11 |
| XAUUSD   |   0.86 |     1.26 |                1.01 |       1.28 |          1.05 |

## 6. Knowledge Extraction Summary
- Successfully exported `knowledge/market_dna.json`
- Successfully exported `knowledge/winning_patterns.json`
- Successfully exported `generated_rules/router_rules.yaml`

### Generated Router Rules (Passed Filters)
```yaml
No combinations passed the strict filters (PF >= 1.20, EV > 0, Trades >= 30, Outlier <= 0.35, Stable)
```

### Top Rejected Rules (Failed Filters but had volume)
None.