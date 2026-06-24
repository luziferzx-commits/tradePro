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
                        prod_probability REAL DEFAULT 0.0,
                        candidate_probability REAL DEFAULT 0.0,
                        probability_gap_abs REAL DEFAULT 0.0,
                        probability_gap_signed REAL DEFAULT 0.0,
                        session_health TEXT NOT NULL,
                        risk_multiplier REAL NOT NULL,
                        decision TEXT NOT NULL,
                        decision_stage TEXT NOT NULL,
                        reasons TEXT,
                        health_dynamic BOOLEAN NOT NULL,
                        health_source TEXT NOT NULL,
                        health_note TEXT,
                        shadow_pnl REAL DEFAULT 0.0,
                        memory_key TEXT,
                        memory_matches INTEGER DEFAULT 0,
                        memory_pf REAL DEFAULT 0.0,
                        memory_win_rate REAL DEFAULT 0.0,
                        memory_expectancy REAL DEFAULT 0.0,
                        memory_confidence TEXT DEFAULT 'UNKNOWN'
                    )
                """)
                
                # Perform auto-migration for existing database
                try:
                    cursor.execute("ALTER TABLE signals ADD COLUMN prod_probability REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN candidate_probability REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN probability_gap_abs REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN probability_gap_signed REAL DEFAULT 0.0")
                except sqlite3.OperationalError:
                    pass
                    
                try:
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_key TEXT")
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_matches INTEGER DEFAULT 0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_pf REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_win_rate REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_expectancy REAL DEFAULT 0.0")
                    cursor.execute("ALTER TABLE signals ADD COLUMN memory_confidence TEXT DEFAULT 'UNKNOWN'")
                except sqlite3.OperationalError:
                    pass
                
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
                        market_score, ml_probability, prod_probability, candidate_probability,
                        probability_gap_abs, probability_gap_signed,
                        session_health, risk_multiplier,
                        decision, decision_stage, reasons, health_dynamic, health_source, health_note,
                        memory_key, memory_matches, memory_pf, memory_win_rate, memory_expectancy, memory_confidence
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    row.get("timestamp"),
                    inserted_at,
                    row.get("symbol"),
                    row.get("session"),
                    row.get("regime"),
                    row.get("market_score"),
                    row.get("ml_probability"),
                    row.get("prod_probability", 0.0),
                    row.get("candidate_probability", 0.0),
                    row.get("probability_gap_abs", 0.0),
                    row.get("probability_gap_signed", 0.0),
                    row.get("session_health"),
                    row.get("risk_multiplier"),
                    row.get("decision"),
                    row.get("decision_stage"),
                    reasons_str,
                    row.get("health_dynamic"),
                    row.get("health_source"),
                    row.get("health_note"),
                    row.get("memory_key"),
                    row.get("memory_matches", 0),
                    row.get("memory_pf", 0.0),
                    row.get("memory_win_rate", 0.0),
                    row.get("memory_expectancy", 0.0),
                    row.get("memory_confidence", "UNKNOWN")
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[Telemetry] Failed to insert signal to DB: {e}. Row data: {row}")
            # Note: Explicitly eating the exception so the scanner never crashes

telemetry_db = TelemetryDatabase()
