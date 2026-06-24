from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
import json

app = FastAPI(title="GoldBot Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "data/telemetry.db"

def query_db(query: str) -> list:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn)
            return df.to_dict(orient="records")
    except Exception as e:
        print(f"DB Query Error: {e}")
        return []

@app.get("/api/summary")
def get_summary():
    data = query_db("""
        SELECT 
            COUNT(*) as total_signals,
            SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted,
            SUM(CASE WHEN decision_stage != 'missing_data' THEN 1 ELSE 0 END) as covered_signals
        FROM signals
    """)
    if not data: return {}
    d = data[0]
    total = d.get('total_signals', 0)
    covered = d.get('covered_signals', 0)
    accepted = d.get('accepted', 0)
    
    return {
        "coverage_pct": round(covered * 100.0 / total, 2) if total > 0 else 0.0,
        "acceptance_pct": round(accepted * 100.0 / total, 2) if total > 0 else 0.0,
        "total_signals": total
    }

@app.get("/api/rejects")
def get_rejects():
    stages = query_db("""
        SELECT decision_stage as stage, COUNT(*) as count
        FROM signals
        WHERE decision = 'REJECT'
        GROUP BY decision_stage
        ORDER BY count DESC
    """)
    reasons = query_db("""
        SELECT reasons as reason, COUNT(*) as count
        FROM signals
        WHERE decision = 'REJECT'
        GROUP BY reasons
        ORDER BY count DESC
        LIMIT 10
    """)
    return {"stages": stages, "reasons": reasons}

@app.get("/api/sessions")
def get_sessions():
    return query_db("""
        SELECT session, COUNT(*) as count,
               SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted
        FROM signals
        GROUP BY session
        ORDER BY count DESC
    """)

@app.get("/api/regimes")
def get_regimes():
    return query_db("""
        SELECT regime, COUNT(*) as count,
               SUM(CASE WHEN decision = 'ACCEPT' THEN 1 ELSE 0 END) as accepted
        FROM signals
        WHERE regime != 'UNKNOWN'
        GROUP BY regime
        ORDER BY count DESC
    """)

@app.get("/api/ml-distribution")
def get_ml_distribution():
    return query_db("""
        SELECT 
            CASE 
                WHEN ml_probability < 0.1 THEN '0.0-0.1'
                WHEN ml_probability < 0.2 THEN '0.1-0.2'
                WHEN ml_probability < 0.3 THEN '0.2-0.3'
                WHEN ml_probability < 0.4 THEN '0.3-0.4'
                WHEN ml_probability < 0.5 THEN '0.4-0.5'
                WHEN ml_probability < 0.6 THEN '0.5-0.6'
                WHEN ml_probability < 0.7 THEN '0.6-0.7'
                WHEN ml_probability < 0.8 THEN '0.7-0.8'
                WHEN ml_probability < 0.9 THEN '0.8-0.9'
                ELSE '0.9-1.0'
            END as prob_bucket,
            COUNT(*) as count
        FROM signals
        WHERE decision_stage != 'missing_data'
        GROUP BY prob_bucket
        ORDER BY prob_bucket
    """)

@app.get("/api/probability-gap")
def get_probability_gap():
    data = query_db("""
        SELECT 
            AVG(probability_gap_abs) as avg_abs_gap,
            AVG(probability_gap_signed) as avg_signed_gap,
            MIN(probability_gap_signed) as min_signed_gap,
            MAX(probability_gap_signed) as max_signed_gap
        FROM signals
        WHERE decision_stage != 'missing_data'
    """)
    if not data: return {}
    return data[0]

@app.get("/api/health")
def get_health():
    # Fetch the latest health state
    data = query_db("""
        SELECT session_health, health_dynamic, timestamp
        FROM signals
        ORDER BY id DESC LIMIT 1
    """)
    if not data: return {"state": "UNKNOWN", "dynamic": False, "days_since_change": 0}
    
    latest = data[0]
    return {
        "state": latest["session_health"],
        "dynamic": latest["health_dynamic"],
        "days_since_change": 0 # Placeholder for actual logic once feedback loop is built
    }

@app.get("/api/latest-signals")
def get_latest_signals():
    return query_db("""
        SELECT timestamp, symbol, session, regime, decision, decision_stage, ml_probability
        FROM signals
        ORDER BY id DESC LIMIT 20
    """)

@app.get("/api/latest-memory")
def get_latest_memory():
    data = query_db("""
        SELECT 
            session, regime, 
            memory_key, memory_matches, memory_pf, memory_confidence
        FROM signals
        ORDER BY id DESC LIMIT 1
    """)
    if not data:
        return {
            "session": "UNKNOWN", "regime": "UNKNOWN", 
            "memory_key": "UNKNOWN", "memory_matches": 0, "memory_pf": 0.0, "memory_confidence": "UNKNOWN"
        }
    return data[0]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("scripts.dashboard_api:app", host="0.0.0.0", port=8000, reload=True)
