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

    # 7. ML Probability Histogram
    run_query("""
        SELECT 
            CASE 
                WHEN ml_probability < 0.1 THEN '0.00 - 0.10'
                WHEN ml_probability < 0.2 THEN '0.10 - 0.20'
                WHEN ml_probability < 0.3 THEN '0.20 - 0.30'
                WHEN ml_probability < 0.4 THEN '0.30 - 0.40'
                WHEN ml_probability < 0.5 THEN '0.40 - 0.50'
                WHEN ml_probability < 0.6 THEN '0.50 - 0.60'
                WHEN ml_probability < 0.7 THEN '0.60 - 0.70'
                WHEN ml_probability < 0.8 THEN '0.70 - 0.80'
                WHEN ml_probability < 0.9 THEN '0.80 - 0.90'
                ELSE '0.90 - 1.00'
            END as prob_bucket,
            COUNT(*) as count
        FROM signals
        WHERE decision_stage != 'missing_data'
        GROUP BY prob_bucket
        ORDER BY prob_bucket
    """, "ML Probability Distribution")

    # 8. Probability Gap (Cand vs Prod)
    run_query("""
        SELECT 
            AVG(probability_gap_abs) as avg_abs_gap,
            AVG(probability_gap_signed) as avg_signed_gap,
            MIN(probability_gap_signed) as min_signed_gap,
            MAX(probability_gap_signed) as max_signed_gap
        FROM signals
        WHERE decision_stage != 'missing_data'
    """, "Probability Gap (Candidate vs Prod)")

if __name__ == "__main__":
    main()
