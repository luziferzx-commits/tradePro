import sqlite3
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TelemetryQueries")

DB_PATH = "data/telemetry.db"

def run_query(query: str, title: str):
    logger.info(f"\n=== {title} ===")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn)
            if df.empty:
                logger.info("No data found.")
            else:
                logger.info(df.to_string(index=False))
    except Exception as e:
        logger.error(f"Failed to execute query: {e}")

def main():
    logger.info("Running Telemetry Summary Queries...")

    # 1. Top Reject Reasons
    run_query("""
        SELECT reasons, COUNT(*) as count, 
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM signals WHERE decision = 'REJECT'), 2) as pct
        FROM signals
        WHERE decision = 'REJECT'
        GROUP BY reasons
        ORDER BY count DESC
        LIMIT 10
    """, "Top Reject Reasons")

    # 2. Top Reject Stages
    run_query("""
        SELECT decision_stage, COUNT(*) as count,
               ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM signals WHERE decision = 'REJECT'), 2) as pct
        FROM signals
        WHERE decision = 'REJECT'
        GROUP BY decision_stage
        ORDER BY count DESC
    """, "Top Reject Stages")

    # 3. Acceptance Rate
    run_query("""
        SELECT 
            COUNT(*) as total_signals,
            SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted,
            ROUND(SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as acceptance_rate_pct
        FROM signals
    """, "Acceptance Rate")

    # 4. Coverage % (Signals processed without missing_data)
    run_query("""
        SELECT 
            COUNT(*) as total_scans,
            SUM(CASE WHEN decision_stage != 'missing_data' THEN 1 ELSE 0 END) as covered_signals,
            ROUND(SUM(CASE WHEN decision_stage != 'missing_data' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as coverage_pct
        FROM signals
    """, "Coverage %")

    # 5. Signals by Session
    run_query("""
        SELECT session, COUNT(*) as count,
               SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted,
               ROUND(SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as accept_pct
        FROM signals
        GROUP BY session
        ORDER BY count DESC
    """, "Signals by Session")

    # 6. Signals by Regime
    run_query("""
        SELECT regime, COUNT(*) as count,
               SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted,
               ROUND(SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as accept_pct
        FROM signals
        WHERE regime != 'UNKNOWN'
        GROUP BY regime
        ORDER BY count DESC
    """, "Signals by Regime")

if __name__ == "__main__":
    main()
