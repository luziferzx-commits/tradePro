# Pattern Discovery Report
*Generated on: 2026-06-25 13:40:56*

## Data Lake Infrastructure
- **Universal Features Saved**: 6000
- **Universal Outcomes Saved**: 46488
- **Patterns Mined**: 5576
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
| RESEARCH_DISCOVERED |         59.82 |            1.58 |           0.27 |

## Top 10 VALIDATED Patterns
None.

## Worst 10 REJECTED Patterns (Blacklist)
|    | symbol   | session_label   | direction   | regime   |   horizon |   occurrences |   profit_factor |   expectancy_r |
|---:|:---------|:----------------|:------------|:---------|----------:|--------------:|----------------:|---------------:|
| 15 | GER40    | LONDON          | LONG        | TREND    |        20 |            53 |            0.39 |          -0.48 |
| 16 | GER40    | LONDON          | LONG        | TREND    |        50 |            53 |            0.39 |          -0.48 |
| 14 | GER40    | LONDON          | LONG        | TREND    |        10 |            53 |            0.42 |          -0.44 |
| 13 | GER40    | LONDON          | LONG        | TREND    |         5 |            53 |            0.44 |          -0.41 |
|  1 | GER40    | ASIA            | LONG        | RANGE    |        10 |            54 |            0.49 |          -0.36 |
| 17 | US500    | LONDON          | SHORT       | RANGE    |         5 |            71 |            0.63 |          -0.24 |
| 19 | US500    | LONDON          | SHORT       | RANGE    |        20 |            71 |            0.63 |          -0.26 |
| 18 | US500    | LONDON          | SHORT       | RANGE    |        10 |            71 |            0.63 |          -0.26 |
| 20 | US500    | LONDON          | SHORT       | RANGE    |        50 |            71 |            0.63 |          -0.26 |
|  3 | GER40    | ASIA            | LONG        | RANGE    |        50 |            54 |            0.63 |          -0.26 |