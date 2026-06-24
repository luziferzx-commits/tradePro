# Incident Report: INC-YYYY-XXX

## 1. Meta
- **Date/Time of Occurrence**: [YYYY-MM-DD HH:MM UTC]
- **Environment**: [Production / Shadow / Demo]
- **Component Affected**: [e.g., MT5 Client, SQLite, XGBoost]

## 2. Symptoms
[Describe what went wrong. e.g., "The bot stopped executing trades and threw a schema error."]

## 3. Impact
[What was the business/trading impact? e.g., "Missed 3 potential trades during London session. No capital lost."]

## 4. Root Cause
[Technical explanation of why it happened. e.g., "The V4.2 upgrade added the 'trend_score' column to TradeSignal, but the production trades.db SQLite file was not migrated."]

## 5. Resolution (Immediate Fix)
[What was done to stop the bleeding? e.g., "Deleted trades.db and allowed the system to recreate the schema automatically."]

## 6. Preventative Measures (Long-term Fix)
[How do we prevent this from happening again? e.g., "Implement Alembic or a database migration script for all future schema changes."]
