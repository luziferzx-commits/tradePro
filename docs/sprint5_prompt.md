Open docs/sprint5_shadow_validation_plan.md and implement Sprint 5 exactly as written.

Goal:
Create Shadow Validation / Observability Pipeline for Candidate V2.1.

Rules:
- Do not change model
- Do not change features
- Do not change thresholds
- Do not retrain
- Do not optimize PF
- Do not enable live real-money trading
- Use config/session_health.v2_1.yaml as frozen config

Implement:
1. Shadow signal logger
2. Daily observability report
3. Health state snapshot
4. Recovery efficiency metrics
5. Health oscillation metrics
6. Signal coverage metrics
7. Days Since Last Change metric
8. Failure condition checker

Output files:
- results/shadow_signals.csv
- results/daily_shadow_report.csv
- results/health_snapshot.csv
- results/health_transitions_live.csv
- results/shadow_failure_flags.csv

After implementation:
Run in shadow mode only.
No real order_send is allowed.
