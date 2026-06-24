import sqlite3
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("GoldBot.Telemetry")

class TelemetryDatabase:
    def __init__(self, db_path="data/telemetry.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Metadata Table for Schema Versioning
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                cursor.execute("INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', '1')")
                
                # Signals Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        inserted_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        session TEXT NOT NULL,
                        regime TEXT NOT NULL,
                        market_score REAL NOT NULL,
                        ml_probability REAL NOT NULL,
                        session_health TEXT NOT NULL,
                        risk_multiplier REAL NOT NULL,
                        decision TEXT NOT NULL,
                        decision_stage TEXT NOT NULL,
                        reasons TEXT,
                        health_dynamic BOOLEAN NOT NULL,
                        health_source TEXT NOT NULL,
                        health_note TEXT,
                        shadow_pnl REAL DEFAULT 0.0
                    )
                """)
                
                # Indexes for query speed
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig_timestamp ON signals(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig_symbol ON signals(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig_session ON signals(session)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig_regime ON signals(regime)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig_decision ON signals(decision)")
                
                conn.commit()
        except Exception as e:
            logger.error(f"[Telemetry] Database initialization failed: {e}")

    def insert_signal(self, row: dict):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert list of reasons to JSON string
                reasons_str = "[]"
                if "reasons" in row and isinstance(row["reasons"], list):
                    reasons_str = json.dumps(row["reasons"])
                elif "reasons" in row and isinstance(row["reasons"], str):
                    reasons_str = json.dumps([row["reasons"]])
                    
                inserted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute("""
                    INSERT INTO signals (
                        timestamp, inserted_at, symbol, session, regime, 
                        market_score, ml_probability, session_health, risk_multiplier,
                        decision, decision_stage, reasons, health_dynamic, health_source, health_note
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    row.get("timestamp"),
                    inserted_at,
                    row.get("symbol"),
                    row.get("session"),
                    row.get("regime"),
                    row.get("market_score"),
                    row.get("ml_probability"),
                    row.get("session_health"),
                    row.get("risk_multiplier"),
                    row.get("decision"),
                    row.get("decision_stage"),
                    reasons_str,
                    row.get("health_dynamic"),
                    row.get("health_source"),
                    row.get("health_note")
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[Telemetry] Failed to insert signal to DB: {e}. Row data: {row}")
            # Note: Explicitly eating the exception so the scanner never crashes

telemetry_db = TelemetryDatabase()
