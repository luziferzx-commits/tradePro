# Pattern Discovery Report
*Generated on: 2026-06-25 11:16:51*

## Data Lake Infrastructure
- **Universal Features Saved**: 681833
- **Universal Outcomes Saved**: 5451136
- **Patterns Mined**: 20736
- **Storage Paths**:
  - Features: `data/feature_store/symbol=.../year=.../*.parquet`
  - Outcomes: `data/outcome_store/symbol=.../year=.../*.parquet`
  - Patterns: `data/pattern_store/pattern_database.parquet`

## Track A: Predefined Strategy Baseline (ABC Engine)
| engine   |   Trades |   PF |   Exp_R |   WinRate |   AvgWin_R |   AvgLoss_R |   Median_R |   MaxDD |   Outlier_Dep |   UniqueFeatures |
|:---------|---------:|-----:|--------:|----------:|-----------:|------------:|-----------:|--------:|--------------:|-----------------:|
| Legacy   |    40372 | 0.98 |   -0.01 |     39.45 |        1.5 |          -1 |         -1 |   779.5 |             0 |                0 |

## Track B: Pattern Discovery Intelligence
*Average performance of discovered edges.*
| promotion_status    |   occurrences |   profit_factor |   expectancy_r |
|:--------------------|--------------:|----------------:|---------------:|
| RESEARCH_DISCOVERED |         71.41 |            1.55 |           0.22 |
| RESEARCH_VALIDATED  |        341.01 |            1.42 |           0.18 |

## Top 10 VALIDATED Patterns
|      | symbol   | session_label   | direction   | regime   |   horizon |   occurrences |   profit_factor |   expectancy_r |
|-----:|:---------|:----------------|:------------|:---------|----------:|--------------:|----------------:|---------------:|
| 1499 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        10 |           152 |            5.23 |           0.65 |
| 1498 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |         5 |           152 |            4.66 |           0.49 |
| 1500 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        20 |           152 |            4.6  |           0.76 |
| 1570 | GBPUSD   | NEW_YORK        | SHORT       | TREND    |        20 |           187 |            3.58 |           0.67 |
| 1569 | GBPUSD   | NEW_YORK        | SHORT       | TREND    |        10 |           187 |            3.35 |           0.51 |
| 1508 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        20 |           261 |            3.34 |           0.69 |
| 1507 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        10 |           261 |            3.33 |           0.57 |
| 1506 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |         5 |           261 |            3.31 |           0.45 |
| 1501 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        50 |           152 |            3.25 |           0.71 |
| 1509 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        50 |           261 |            3.11 |           0.69 |

## Worst 10 REJECTED Patterns (Blacklist)
|       | symbol   | session_label   | direction   | regime   |   horizon |   occurrences |   profit_factor |   expectancy_r |
|------:|:---------|:----------------|:------------|:---------|----------:|--------------:|----------------:|---------------:|
|  6276 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        50 |           152 |            0.07 |          -0.88 |
|  6275 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        20 |           152 |            0.07 |          -0.85 |
| 11339 | XAUUSD   | NEW_YORK        | SHORT       | TREND    |        50 |            52 |            0.09 |          -0.86 |
|  6274 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        10 |           152 |            0.1  |          -0.67 |
| 11337 | XAUUSD   | NEW_YORK        | SHORT       | TREND    |        10 |            52 |            0.11 |          -0.61 |
| 11338 | XAUUSD   | NEW_YORK        | SHORT       | TREND    |        20 |            52 |            0.11 |          -0.74 |
|  6273 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |         5 |           152 |            0.16 |          -0.51 |
|  9556 | USDJPY   | NEW_YORK        | LONG        | TREND    |        50 |           155 |            0.16 |          -0.76 |
|  9554 | USDJPY   | NEW_YORK        | LONG        | TREND    |        10 |           155 |            0.18 |          -0.69 |
| 11272 | XAUUSD   | NEW_YORK        | LONG        | TREND    |        10 |            61 |            0.18 |          -0.52 |