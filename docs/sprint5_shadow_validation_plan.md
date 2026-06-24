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
     - **Signal Coverage:** Signals Generated, Signals Executed, Coverage % (e.g., target > 60%).
     - **Performance Metrics:** PF, Win Rate, Max DD (Overall and per-window/period).
     - **Recovery Efficiency:** Disabled Count, Recovered Count, Recovery Success Rate, Average Recovery Time (to ensure the logic actually recovers).
     - **Health Oscillation Tracking:** Track specific state transitions (e.g., `HEALTHY -> DISABLED`, `DISABLED -> HEALTHY`) to detect dangerous flip-flopping within short timeframes.
     - **Opportunity Cost Analysis:** Top Disabled Contexts, Top Opportunity Cost Contexts, Top Saved Loss Contexts.
     - **Live Health Snapshot:** A clear, readable table showing the current state of every Context (e.g., `Asia + NORMAL: HEALTHY`, `London + CHOPPY: DISABLED`).
4. **Comparison Metrics:**
   - `baseline shadow PnL` (Without Risk Layer)
   - `session-health adjusted PnL` (With V2.1 Risk Layer)
   - `missed opportunity`
   - `saved loss`
5. **Promotion Rules (Acceptance Criteria for Sprint 6 - Capital Allocation):**
   - Minimum 4 weeks of paper/shadow validation.
   - PF >= 1.50
   - Signal Coverage > 60%
   - Max DD controlled.
   - Health states do not oscillate rapidly.
   - No critical runtime bugs.

## Definition of Failure (Shadow Validation Failure Conditions)
It is equally important to define what constitutes a failure so that we can decisively reject the model without debate if real-world data turns hostile. The Shadow Validation will be considered a **FAILURE** if any of the following occur:
1. **PF < 1.20** for 2 consecutive weeks.
2. **Coverage < 50%** (The system is skipping too many trades and becoming overly conservative).
3. **Health Oscillation exceeds threshold** (e.g., > 20 state flips per week, indicating unstable context definition).
4. **Recovery Success Rate < 30%** (When the system re-enables risk, it immediately loses and disables again).
5. **Runtime errors** affecting execution logic.
6. **Max DD exceeds expected backtest envelope** (e.g., DD breaches the -10R threshold we optimized for).

## Anti-Goals for Sprint 5
❌ Do NOT add new indicators.
❌ Do NOT add new feature engineering.
❌ Do NOT add new models.
❌ Do NOT retrain the model.
❌ Do NOT optimize for PF.
**Mantra:** *Observe, Measure, Validate.*

## Lookahead: Sprint 6 (Capital Allocation Framework)
If and only if Candidate V2.1 passes the 4-week Shadow Validation, we will proceed to Sprint 6 to build the Capital Allocation Framework (e.g., starting at 0.25% risk -> 0.5% -> 0.75% -> 1.0% based on live performance). 

**Status:**
Pending kickoff in the next Sprint. Current baseline remains **Candidate V2.1**.
