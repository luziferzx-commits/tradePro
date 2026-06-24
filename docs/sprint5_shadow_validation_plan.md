# Next Sprint: Shadow Validation Pipeline

**Goal:** 
Validate Candidate V2.1 on paper/live-forward data before approving any real-money live trading.

## Tasks
1. **Create Shadow/Live-Forward Validation Script:**
   - Build a pipeline that simulates real-time ingestion of signals against Candidate V2.1 rules.
2. **Signal Logging:**
   - Log every signal precisely:
     - `raw signal`
     - `session` / `regime`
     - `health state`
     - `risk multiplier`
     - `adjusted risk`
     - `theoretical PnL`
     - `executed_or_skipped`
3. **Reporting:**
   - Generate daily and weekly performance reports.
4. **Comparison Metrics:**
   - `baseline shadow PnL` (Without Risk Layer)
   - `session-health adjusted PnL` (With V2.1 Risk Layer)
   - `missed opportunity`
   - `saved loss`
5. **Promotion Rules (Acceptance Criteria):**
   - Minimum 4 weeks of paper/shadow validation.
   - PF >= 1.50
   - Max DD controlled.
   - Skipped trades <= 35%.
   - No critical runtime bugs.

**Status:**
Pending kickoff in the next Sprint. Current baseline remains **Candidate V2.1**.
