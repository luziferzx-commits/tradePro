# Market Intelligence Report
*Generated on: 2026-06-25 10:41:13*

> [!WARNING]
> **RESEARCH_EXECUTION_MODEL = candle_close_fill**
> `spread_model = SIMULATED_DYNAMIC_ATR_BASED`.

## 1. Engine Benchmark
|    | engine   |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|:---------|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 | Legacy   |    40372 | 1.02 |   -0.01 |         -1 |     39.45 |     1.5 | 23325.5 |            1.5 |             0 |

## 2. Time Robustness (Yearly Impact)
|    |   year |   Trades |   PF |   Exp_R |   Median_R |   WinRate |   AvgRR |   MaxDD |   Max_1Trade_R |   Outlier_Dep |
|---:|-------:|---------:|-----:|--------:|-----------:|----------:|--------:|--------:|---------------:|--------------:|
|  0 |   2025 |    25026 | 1.03 |   -0.01 |         -1 |     39.48 |     1.5 | 23325.5 |            1.5 |             0 |
|  1 |   2026 |    15346 | 1.01 |   -0.01 |         -1 |     39.4  |     1.5 | 17652.6 |            1.5 |             0 |

## 3. Stability Test (Progressive Chunks)
|    | symbol   | session   | strategy                      |   trades |   pf | verdict   | pfs_progression                                                                            |
|---:|:---------|:----------|:------------------------------|---------:|-----:|:----------|:-------------------------------------------------------------------------------------------|
|  0 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       49 | 0.92 | UNSTABLE  | [np.float64(0.0), np.float64(1.23), np.float64(1.52), np.float64(1.01), np.float64(0.92)]  |
|  1 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       83 | 1.32 | STABLE    | [np.float64(1.31), np.float64(1.87), np.float64(1.72), np.float64(1.58), np.float64(1.32)] |
|  2 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       32 | 0.78 | UNSTABLE  | [np.float64(0.32), np.float64(0.57), np.float64(0.85), np.float64(0.66), np.float64(0.78)] |
|  3 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       86 | 1.13 | STABLE    | [np.float64(2.07), np.float64(2.37), np.float64(1.66), np.float64(1.26), np.float64(1.13)] |
|  4 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       70 | 1.41 | STABLE    | [np.float64(2.0), np.float64(0.98), np.float64(1.57), np.float64(1.58), np.float64(1.41)]  |
|  5 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       46 | 1.18 | STABLE    | [np.float64(0.94), np.float64(2.64), np.float64(0.97), np.float64(0.94), np.float64(1.18)] |
|  6 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       80 | 2.08 | STABLE    | [np.float64(1.79), np.float64(1.78), np.float64(2.03), np.float64(2.01), np.float64(2.08)] |
|  7 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       58 | 0.91 | UNSTABLE  | [np.float64(1.92), np.float64(2.31), np.float64(1.75), np.float64(1.27), np.float64(0.91)] |
|  8 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       65 | 0.68 | UNSTABLE  | [np.float64(1.18), np.float64(1.47), np.float64(0.89), np.float64(0.63), np.float64(0.68)] |
|  9 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       42 | 1.38 | STABLE    | [np.float64(1.48), np.float64(1.16), np.float64(1.48), np.float64(1.49), np.float64(1.38)] |
| 10 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       54 | 1.29 | STABLE    | [np.float64(0.41), np.float64(1.36), np.float64(1.79), np.float64(1.4), np.float64(1.29)]  |
| 11 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       43 | 1.33 | STABLE    | [np.float64(0.95), np.float64(1.16), np.float64(1.28), np.float64(1.35), np.float64(1.33)] |
| 12 | BTCUSD   | ASIA      | Volatility Expansion Breakout |       39 | 0.65 | UNSTABLE  | [np.float64(8.5), np.float64(1.94), np.float64(1.41), np.float64(1.12), np.float64(0.65)]  |
| 13 | BTCUSD   | LONDON    | London Breakout               |      129 | 0.87 | UNSTABLE  | [np.float64(0.57), np.float64(0.85), np.float64(0.94), np.float64(0.81), np.float64(0.87)] |
| 14 | BTCUSD   | LONDON    | London Breakout               |       92 | 1.23 | STABLE    | [np.float64(1.11), np.float64(0.74), np.float64(0.88), np.float64(0.95), np.float64(1.23)] |
| 15 | BTCUSD   | LONDON    | London Breakout               |      112 | 1    | DECAYING  | [np.float64(2.02), np.float64(1.45), np.float64(1.08), np.float64(0.91), np.float64(1.0)]  |
| 16 | BTCUSD   | LONDON    | London Breakout               |       81 | 0.96 | UNSTABLE  | [np.float64(1.18), np.float64(1.38), np.float64(1.11), np.float64(1.13), np.float64(0.96)] |
| 17 | BTCUSD   | LONDON    | London Breakout               |       85 | 1.46 | STABLE    | [np.float64(0.46), np.float64(0.69), np.float64(1.05), np.float64(1.32), np.float64(1.46)] |
| 18 | BTCUSD   | LONDON    | London Breakout               |      102 | 1.06 | STABLE    | [np.float64(0.65), np.float64(1.08), np.float64(0.91), np.float64(0.78), np.float64(1.06)] |
| 19 | BTCUSD   | LONDON    | London Breakout               |       49 | 0.92 | UNSTABLE  | [np.float64(3.1), np.float64(2.3), np.float64(0.98), np.float64(1.03), np.float64(0.92)]   |

## 4. Market DNA Profiles
### XAUUSD
- **Best Session**: OFF_SESSION
- **Core Strategy**: Volatility Expansion Breakout
- **Optimal Volatility**: Low
### BTCUSD
- **Best Session**: ASIA
- **Core Strategy**: Volatility Expansion Breakout
- **Optimal Volatility**: Extreme
### EURUSD
- **Best Session**: OFF_SESSION
- **Core Strategy**: RSI Exhaustion Reversal
- **Optimal Volatility**: High
### GBPUSD
- **Best Session**: ASIA
- **Core Strategy**: RSI Exhaustion Reversal
- **Optimal Volatility**: High
### NAS100
- **Best Session**: ASIA
- **Core Strategy**: Volatility Expansion Breakout
- **Optimal Volatility**: High
### USDJPY
- **Best Session**: LONDON
- **Core Strategy**: London Breakout
- **Optimal Volatility**: Extreme
### ETHUSD
- **Best Session**: LONDON_NY_OVERLAP
- **Core Strategy**: NY Breakout
- **Optimal Volatility**: Extreme

## 5. Symbol × Session Profit Factor Heatmap
| symbol   |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:---------|-------:|---------:|--------------------:|-----------:|--------------:|
| BTCUSD   |   1.18 |     0.99 |                1.03 |       0.94 |          1.09 |
| ETHUSD   |   0.99 |     0.93 |                1.14 |       1.13 |          0.81 |
| EURUSD   |   0.9  |     0.94 |                0.89 |       0.87 |          0.89 |
| GBPUSD   |   1    |     0.93 |                0.97 |       0.94 |          0.63 |
| NAS100   |   1.17 |     0.97 |                0.94 |       1    |          1.52 |
| USDJPY   |   0.85 |     1.08 |                0.92 |       0.94 |          0.89 |
| XAUUSD   |   1    |     0.97 |                0.94 |       0.72 |          1.57 |

## 6. Knowledge Extraction Summary
- Successfully exported `knowledge/market_dna.json`
- Successfully exported `knowledge/winning_patterns.json`
- Successfully exported `generated_rules/router_rules.yaml`

### Generated Router Rules (Passed Filters)
```yaml
BTCUSD:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 2.084545073658067
    expectancy_r: 0.14457831325301612
    trade_count: 83
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - &id001 !!python/object/apply:numpy.dtype
      args:
      - f8
      - false
      - true
      state: !!python/tuple
      - 3
      - <
      - null
      - null
      - null
      - -1
      - -1
      - 0
    - !!binary |
      XI/C9Shc7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:00.205143'
  LONDON:
    preferred_strategy: London Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Rising (20-25)
    historical_pf: 1.4631383374072633
    expectancy_r: 0.14130434782609183
    trade_count: 92
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      XI/C9Shc7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:00.399421'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Low
    adx_bucket: Weak (<20)
    historical_pf: 1.85897760511687
    expectancy_r: 0.14754098360656148
    trade_count: 61
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:00.934876'
  NEW_YORK:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 1.8072629683872554
    expectancy_r: 0.36363636363636415
    trade_count: 44
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:01.477284'
ETHUSD:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: High
    adx_bucket: Strong (25-40)
    historical_pf: 1.9804268440143686
    expectancy_r: 0.1507936507936494
    trade_count: 63
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:01.987684'
  LONDON:
    preferred_strategy: London Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Medium
    adx_bucket: Weak (<20)
    historical_pf: 1.562825689156668
    expectancy_r: 0.3084112149532725
    trade_count: 107
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:02.384781'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Extreme
    adx_bucket: Weak (<20)
    historical_pf: 2.0445753307373087
    expectancy_r: 0.25000000000000083
    trade_count: 50
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:02.946814'
  NEW_YORK:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 2.3153818025889907
    expectancy_r: 0.3372093023255821
    trade_count: 43
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      XI/C9Shc7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:03.444478'
EURUSD:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Extreme (>40)
    historical_pf: 2.9506402206828115
    expectancy_r: 0.3349514563106928
    trade_count: 103
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:04.034100'
  LONDON:
    preferred_strategy: London Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: High
    adx_bucket: Weak (<20)
    historical_pf: 1.5325049452680395
    expectancy_r: 0.1904761904761969
    trade_count: 63
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:04.326135'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Extreme
    adx_bucket: Extreme (>40)
    historical_pf: 1.3177818222888091
    expectancy_r: 0.1274509803921638
    trade_count: 51
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:05.057077'
  NEW_YORK:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: High
    adx_bucket: Strong (25-40)
    historical_pf: 1.8232239801651784
    expectancy_r: 0.1250000000000282
    trade_count: 40
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      FK5H4XoU7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:05.599566'
  OFF_SESSION:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Low
    adx_bucket: Strong (25-40)
    historical_pf: 1.4105233612689936
    expectancy_r: 0.04166666666660443
    trade_count: 36
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:05.812755'
GBPUSD:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Strong (25-40)
    historical_pf: 1.3777429749636052
    expectancy_r: 0.18421052631579587
    trade_count: 57
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:06.025981'
  LONDON:
    preferred_strategy: London Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Low
    adx_bucket: Rising (20-25)
    historical_pf: 1.6493052612315802
    expectancy_r: 0.3414634146341307
    trade_count: 41
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:06.199541'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: High
    adx_bucket: Weak (<20)
    historical_pf: 2.043689730804407
    expectancy_r: 0.21951219512195486
    trade_count: 41
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      XI/C9Shc7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:06.823697'
NAS100:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Extreme (>40)
    historical_pf: 2.4349913235748395
    expectancy_r: 0.2686567164179202
    trade_count: 67
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:07.807667'
  LONDON:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: High
    adx_bucket: Strong (25-40)
    historical_pf: 1.4317315485691102
    expectancy_r: 0.2062937062937125
    trade_count: 143
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      FK5H4XoU7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:08.019229'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - TREND
    atr_bucket: High
    adx_bucket: Strong (25-40)
    historical_pf: 1.6127185226808087
    expectancy_r: 0.13636363636362764
    trade_count: 55
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:08.656444'
  NEW_YORK:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 2.259557713917214
    expectancy_r: 0.04166666666666726
    trade_count: 48
    stability_verdict: HIGH_VARIANCE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:09.136417'
USDJPY:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Extreme (>40)
    historical_pf: 1.522282881053981
    expectancy_r: 0.2921348314606863
    trade_count: 89
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      XI/C9Shc7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:09.881758'
  LONDON:
    preferred_strategy: London Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 2.867246074706635
    expectancy_r: 0.1702127659574126
    trade_count: 47
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      CtejcD0K7z8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:10.091103'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - TREND
    atr_bucket: High
    adx_bucket: Strong (25-40)
    historical_pf: 1.59230309612928
    expectancy_r: 0.18217054263565566
    trade_count: 129
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:10.813694'
  NEW_YORK:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Strong (25-40)
    historical_pf: 1.29798101625314
    expectancy_r: 0.12903225806455712
    trade_count: 31
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      w/UoXI/C7T8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:11.414583'
XAUUSD:
  ASIA:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Strong (25-40)
    historical_pf: 1.8704134936823262
    expectancy_r: 0.14457831325302267
    trade_count: 83
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:11.904701'
  LONDON:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Low
    adx_bucket: Strong (25-40)
    historical_pf: 2.1060188133455573
    expectancy_r: 0.2650602409638537
    trade_count: 83
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:12.261757'
  LONDON_NY_OVERLAP:
    preferred_strategy: NY Breakout
    allowed_regimes:
    - RANGE
    atr_bucket: Medium
    adx_bucket: Rising (20-25)
    historical_pf: 1.8051283524252286
    expectancy_r: 0.375
    trade_count: 40
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:12.815557'
  NEW_YORK:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Low
    adx_bucket: Strong (25-40)
    historical_pf: 1.2728353727339228
    expectancy_r: 0.10169491525423643
    trade_count: 59
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      uB6F61G47j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:13.595748'
  OFF_SESSION:
    preferred_strategy: Volatility Expansion Breakout
    allowed_regimes:
    - TREND
    atr_bucket: Extreme
    adx_bucket: Strong (25-40)
    historical_pf: 2.428028051397374
    expectancy_r: 0.3333333333333176
    trade_count: 45
    stability_verdict: STABLE
    confidence_score: !!python/object/apply:numpy._core.multiarray.scalar
    - *id001
    - !!binary |
      ZmZmZmZm7j8=
    promotion_status: RESEARCH_VALIDATED
    shadow_passed: false
    live_passed: false
    source_report: MARKET_INTELLIGENCE_REPORT_V2
    generated_at: '2026-06-25T10:41:13.783211'

```

### Top Rejected Rules (Failed Filters but had volume)
|     | symbol   | session           | strategy                      |   trades |   pf | verdict       | reason   |
|----:|:---------|:------------------|:------------------------------|---------:|-----:|:--------------|:---------|
|  79 | ETHUSD   | LONDON_NY_OVERLAP | NY Breakout                   |       39 | 1.2  | STABLE        | Low PF   |
| 292 | USDJPY   | NEW_YORK          | Volatility Expansion Breakout |       50 | 1.2  | STABLE        | Low PF   |
| 222 | NAS100   | LONDON_NY_OVERLAP | NY Breakout                   |      130 | 1.19 | STABLE        | Low PF   |
| 158 | GBPUSD   | LONDON            | Volatility Expansion Breakout |       45 | 1.19 | STABLE        | Low PF   |
|  67 | ETHUSD   | LONDON_NY_OVERLAP | NY Breakout                   |       52 | 1.19 | STABLE        | Low PF   |
| 193 | NAS100   | LONDON            | London Breakout               |       34 | 1.19 | STABLE        | Low PF   |
|  16 | BTCUSD   | LONDON            | London Breakout               |       89 | 1.18 | STABLE        | Low PF   |
|  82 | ETHUSD   | NEW_YORK          | Volatility Expansion Breakout |       32 | 1.18 | HIGH_VARIANCE | Low PF   |
|   3 | BTCUSD   | ASIA              | Volatility Expansion Breakout |       46 | 1.18 | STABLE        | Low PF   |
|  30 | BTCUSD   | LONDON_NY_OVERLAP | NY Breakout                   |       74 | 1.17 | STABLE        | Low PF   |