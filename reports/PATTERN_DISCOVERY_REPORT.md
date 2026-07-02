# Pattern Discovery Report
*Generated on: 2026-06-26 19:39:38*

## Data Lake Infrastructure
- **Universal Features Saved**: 873689
- **Universal Outcomes Saved**: 6985984
- **Patterns Mined**: 21000
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
| RESEARCH_DISCOVERED |         71.97 |            1.56 |           0.23 |
| RESEARCH_VALIDATED  |        374.79 |            1.43 |           0.18 |

## Top 10 VALIDATED Patterns
|      | symbol   | session_label   | direction   | regime   |   horizon |   occurrences |   profit_factor |   expectancy_r |
|-----:|:---------|:----------------|:------------|:---------|----------:|--------------:|----------------:|---------------:|
| 1436 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        10 |           152 |            5.23 |           0.65 |
| 1435 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |         5 |           152 |            4.66 |           0.49 |
| 1437 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        20 |           152 |            4.6  |           0.76 |
| 1507 | GBPUSD   | NEW_YORK        | SHORT       | TREND    |        20 |           187 |            3.58 |           0.67 |
| 1444 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        10 |           260 |            3.39 |           0.58 |
| 1445 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        20 |           260 |            3.38 |           0.69 |
| 1506 | GBPUSD   | NEW_YORK        | SHORT       | TREND    |        10 |           187 |            3.35 |           0.51 |
| 1443 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |         5 |           260 |            3.31 |           0.46 |
| 1438 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        50 |           152 |            3.25 |           0.71 |
| 1446 | GBPUSD   | NEW_YORK        | SHORT       | RANGE    |        50 |           260 |            3.14 |           0.69 |

## Worst 10 REJECTED Patterns (Blacklist)
|       | symbol   | session_label   | direction   | regime   |   horizon |   occurrences |   profit_factor |   expectancy_r |
|------:|:---------|:----------------|:------------|:---------|----------:|--------------:|----------------:|---------------:|
|  6771 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        50 |           152 |            0.07 |          -0.88 |
|  6770 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        20 |           152 |            0.07 |          -0.85 |
|  6769 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |        10 |           152 |            0.1  |          -0.67 |
|  6768 | GBPUSD   | NEW_YORK        | LONG        | RANGE    |         5 |           152 |            0.16 |          -0.51 |
| 10060 | USDJPY   | NEW_YORK        | LONG        | TREND    |        50 |           155 |            0.16 |          -0.76 |
| 10058 | USDJPY   | NEW_YORK        | LONG        | TREND    |        10 |           155 |            0.18 |          -0.69 |
| 10059 | USDJPY   | NEW_YORK        | LONG        | TREND    |        20 |           155 |            0.18 |          -0.72 |
|  5218 | EURUSD   | NEW_YORK        | LONG        | RANGE    |        50 |            56 |            0.18 |          -0.73 |
|  8533 | NAS100   | OFF_SESSION     | LONG        | RANGE    |        10 |            68 |            0.18 |          -0.51 |
|  8534 | NAS100   | OFF_SESSION     | LONG        | RANGE    |        20 |            68 |            0.19 |          -0.61 |