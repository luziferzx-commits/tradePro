# Research Campaign v2: Dimensional Edge Analysis

*Generated on: 2026-06-25 10:06:13*
**RESEARCH_EXECUTION_MODEL = candle_close_fill**
*Note: This is a dimensional research simulation approximating execution at candle close. This is NOT a production-grade tick backtest. Profitability shown is for edge-discovery purposes only.*

## 1. Router Engine Benchmark
| Engine | Trades | PF | Exp R | Win Rate | Avg RR | Max DD |
|---|---|---|---|---|---|---|
| Legacy | 57 | 0.84 | -0.12 | 35.1% | 1.50 | 186.75 |

---
*The following dimensional analysis uses the `ABC+Session` engine.*

## 2. Performance by Session
|    | session           |   Trades |   PF |   Exp_R |   WinRate |   AvgRR |   MaxDD |
|---:|:------------------|---------:|-----:|--------:|----------:|--------:|--------:|
|  0 | ASIA              |       13 | 1.81 |    0.35 |     53.85 |     1.5 |   28.94 |
|  1 | LONDON            |       26 | 1.52 |    0.15 |     46.15 |     1.5 |   56.39 |
|  2 | LONDON_NY_OVERLAP |       12 | 0    |   -1    |      0    |     0   |  118.16 |
|  3 | NEW_YORK          |        2 | 0    |   -1    |      0    |     0   |    7.66 |
|  4 | OFF_SESSION       |        4 | 0.38 |   -0.38 |     25    |     1.5 |   13.4  |

## 3. Performance by Symbol
|    | symbol   |   Trades |   PF |   Exp_R |   WinRate |   AvgRR |   MaxDD |
|---:|:---------|---------:|-----:|--------:|----------:|--------:|--------:|
|  0 | XAUUSD   |       57 | 0.84 |   -0.12 |     35.09 |     1.5 |  186.75 |

## 4. Session × Symbol (PF Matrix)
| symbol   |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:---------|-------:|---------:|--------------------:|-----------:|--------------:|
| XAUUSD   |   1.81 |     1.52 |                   0 |          0 |          0.38 |

## 5. Strategy × Session (PF Matrix)
| strategy                      |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:------------------------------|-------:|---------:|--------------------:|-----------:|--------------:|
| London Breakout               | nan    |     0.77 |                 nan |        nan |        nan    |
| NY Breakout                   | nan    |   nan    |                   0 |          0 |        nan    |
| RSI Exhaustion Reversal       | nan    |   nan    |                   0 |        nan |        nan    |
| Volatility Expansion Breakout |   1.81 |     4.41 |                   0 |        nan |          0.38 |

## 6. Regime × Session (PF Matrix)
| regime   |   ASIA |   LONDON |   LONDON_NY_OVERLAP |   NEW_YORK |   OFF_SESSION |
|:---------|-------:|---------:|--------------------:|-----------:|--------------:|
| RANGE    |   0.95 |     2.54 |                   0 |          0 |          0.56 |
| TREND    |   2.75 |     0.19 |                   0 |          0 |          0    |

## 7. Performance by Hour (UTC)
|    |   hour |   Trades |    PF |   Exp_R |   WinRate |   AvgRR |   MaxDD |
|---:|-------:|---------:|------:|--------:|----------:|--------:|--------:|
|  0 |      0 |        5 | 99    |    1.5  |     100   |     1.5 |    0    |
|  1 |      1 |        1 |  0    |   -1    |       0   |     0   |    0    |
|  2 |      2 |        1 | 99    |    1.5  |     100   |     1.5 |    0    |
|  3 |      3 |        2 |  1.47 |    0.25 |      50   |     1.5 |    9.59 |
|  4 |      4 |        1 |  0    |   -1    |       0   |     0   |    0    |
|  5 |      6 |        3 |  0    |   -1    |       0   |     0   |   18.08 |
|  6 |      7 |        5 |  0    |   -1    |       0   |     0   |   35.5  |
|  7 |      8 |        1 |  0    |   -1    |       0   |     0   |    0    |
|  8 |      9 |        8 |  2.62 |    0.56 |      62.5 |     1.5 |   15.46 |
|  9 |     10 |        4 |  0.53 |   -0.37 |      25   |     1.5 |   14.87 |
| 10 |     11 |        4 |  1.38 |    0.25 |      50   |     1.5 |   16.99 |
| 11 |     12 |        4 | 99    |    1.5  |     100   |     1.5 |    0    |
| 12 |     13 |        9 |  0    |   -1    |       0   |     0   |   88.03 |
| 13 |     14 |        1 |  0    |   -1    |       0   |     0   |    0    |
| 14 |     15 |        2 |  0    |   -1    |       0   |     0   |    9.54 |
| 15 |     16 |        2 |  0    |   -1    |       0   |     0   |    7.66 |
| 16 |     22 |        2 |  1.22 |    0.25 |      50   |     1.5 |    6.2  |
| 17 |     23 |        2 |  0    |   -1    |       0   |     0   |    7.2  |

## 8. Performance by Weekday (0=Mon, 4=Fri)
|    |   weekday |   Trades |   PF |   Exp_R |   WinRate |   AvgRR |   MaxDD |
|---:|----------:|---------:|-----:|--------:|----------:|--------:|--------:|
|  0 |         0 |       19 | 0.82 |   -0.21 |     31.58 |     1.5 |   91.4  |
|  1 |         1 |       20 | 0.44 |   -0.38 |     25    |     1.5 |  106.79 |
|  2 |         2 |       15 | 2.05 |    0.5  |     60    |     1.5 |   33.32 |
|  3 |         4 |        2 | 0    |   -1    |      0    |     0   |    6.02 |
|  4 |         6 |        1 | 0    |   -1    |      0    |     0   |    0    |

---

## 9. Best Combinations Leaderboard (Min 30 Trades)
| combo   | Trades   | PF   | Exp_R   | WinRate   | AvgRR   | MaxDD   |
|---------|----------|------|---------|-----------|---------|---------|

## 10. Worst Combinations Leaderboard (Min 30 Trades)
| combo   | Trades   | PF   | Exp_R   | WinRate   | AvgRR   | MaxDD   |
|---------|----------|------|---------|-----------|---------|---------|

