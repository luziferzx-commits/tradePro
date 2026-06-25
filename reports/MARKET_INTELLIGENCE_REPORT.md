# Market Intelligence Report
*Generated on: 2026-06-25 10:11:28*

> [!WARNING]
> **RESEARCH_EXECUTION_MODEL = candle_close_fill**
> This report uses a simplified execution model for edge-discovery. 
> `spread_model = SIMULATED_DYNAMIC_ATR_BASED` (`spread_is_simulated = True`). This is NOT broker-real spread data.

## 1. Engine Benchmark
|    | engine   |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:---------|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Legacy   |      231 | 1.03 |    0.01 |         -1 |     40.26 |     1.5 |  186.75 |            1.5 |          0.01 |

## 2. Market DNA Profiles
### XAUUSD
- **Best Session**: LONDON
- **Core Strategy**: London Breakout
- **Regime**: TREND
- **Optimal Volatility**: Medium ATR

### EURUSD
- **Best Session**: ASIA
- **Core Strategy**: London Breakout
- **Regime**: RANGE
- **Optimal Volatility**: High ATR

## 3. Symbol × Session Profit Factor Heatmap
| symbol   |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:---------|-------:|---------:|--------------------:|-----------:|--------------:|
| EURUSD   |   3.55 |     1.08 |                0.65 |       0.43 |          0    |
| XAUUSD   |   1.61 |     2.02 |                0.45 |       0.35 |          0.99 |

## 4. Feature Impact Analysis
### By ATR (Volatility)
|    | ATR_Bucket   |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:-------------|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Low          |       58 | 1.02 |    0.08 |         -1 |     43.1  |     1.5 |   55.38 |            1.5 |          0.04 |
|  1 | Medium       |       58 | 1.98 |    0.03 |         -1 |     41.38 |     1.5 |   39.5  |            1.5 |          0.04 |
|  2 | High         |       57 | 0.95 |    0.05 |         -1 |     42.11 |     1.5 |   50.06 |            1.5 |          0.04 |
|  3 | Extreme      |       58 | 0.76 |   -0.14 |         -1 |     34.48 |     1.5 |  138.35 |            1.5 |          0.05 |

### By ADX (Momentum)
|    | ADX_Bucket     |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:---------------|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Weak (<20)     |       33 | 0.82 |   -0.09 |         -1 |     36.36 |     1.5 |   83.12 |            1.5 |          0.08 |
|  1 | Rising (20-25) |       36 | 1.87 |    0.04 |         -1 |     41.67 |     1.5 |   24.43 |            1.5 |          0.07 |
|  2 | Strong (25-40) |      104 | 1    |    0.03 |         -1 |     41.35 |     1.5 |  132.81 |            1.5 |          0.02 |
|  3 | Extreme (>40)  |       58 | 1.01 |   -0.01 |         -1 |     39.66 |     1.5 |   70.43 |            1.5 |          0.04 |

### By Trend (EMA50 Slope)
|    | Trend_Bucket   |   Trades |       PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:---------------|---------:|---------:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Strong Down    |      139 |     0.95 |    0.04 |       -1   |     41.73 |     1.5 |  137.44 |            1.5 |          0.02 |
|  1 | Down           |        5 | 26896    |    1    |        1.5 |     80    |     1.5 |    0    |            1.5 |          0.25 |
|  2 | Flat           |        7 |     0.63 |   -0.29 |       -1   |     28.57 |     1.5 |    8.55 |            1.5 |          0.5  |
|  3 | Up             |       11 |     2.04 |    0.14 |       -1   |     45.45 |     1.5 |    6.49 |            1.5 |          0.2  |
|  4 | Strong Up      |       66 |     1.16 |   -0.13 |       -1   |     34.85 |     1.5 |  101.31 |            1.5 |          0.04 |

## 5. Top 20 Winning Patterns (Min 30 Trades)
*Identified strong edges in the market structure.*
No patterns reached 30 trades yet.

## 6. Top 20 Losing Patterns & Failure Analysis (Min 30 Trades)
*Identified leaks in the strategy execution.*
No patterns reached 30 trades yet.
