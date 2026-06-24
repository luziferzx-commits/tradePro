# Next Sprint: Shadow Validation Pipeline

**Goal:** 
Validate Candidate V2.1 on paper/live-forward data before approving any real-money live trading. The primary focus of this sprint is **Observability**, not adding new models or features. We must prove the system can survive in the real world.

## Capital Allocation Status
```text
Research Status: APPROVED
Backtest Status: APPROVED
OOS Status: APPROVED
Forward Test Status: PENDING
Capital Allocation: 0%
```

## Tasks
1. **Create Shadow/Live-Forward Validation Script:**
   - Build a pipeline that simulates real-time ingestion of signals against Candidate V2.1 rules.
2. **Signal Logging (Granular Tracking):**
   - Log every signal precisely:
     - `raw signal`
     - `session` / `regime`
     - `health state`
     - `risk multiplier`
     - `adjusted risk`
     - `theoretical PnL`
     - `executed_or_skipped`
3. **Observability Dashboard (Daily/Weekly):**
   - The primary engineering task is to build a dashboard reporting:
     - Date
     - Signals / Executed / Skipped
     - Health State Distribution
     - PF / Win Rate / Max DD
     - Top Disabled Contexts
     - Top Opportunity Cost Contexts
     - Current Session Health Table (Live state tracking)
4. **Comparison Metrics:**
   - `baseline shadow PnL` (Without Risk Layer)
   - `session-health adjusted PnL` (With V2.1 Risk Layer)
   - `missed opportunity`
   - `saved loss`
5. **Promotion Rules (Acceptance Criteria):**
   - Minimum 4 weeks of paper/shadow validation.
   - PF >= 1.50
   - Max DD controlled.
   - Skipped trades <= 35% (Monitor if the 30% holds true).
   - No critical runtime bugs.
   - Monitor for excessive oscillation or rapid disable/recover flip-flopping.

**Status:**
Pending kickoff in the next Sprint. Current baseline remains **Candidate V2.1**.
