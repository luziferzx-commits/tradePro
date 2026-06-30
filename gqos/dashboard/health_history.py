import sqlite3
import pandas as pd
import json
import logging
from datetime import datetime, timedelta
import os
import uuid

logger = logging.getLogger("HealthHistory")

DB_PATH = "gqos_research.db"

def init_db(db_path=DB_PATH):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edge_health_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                overall_edge REAL,
                alpha_health REAL,
                execution_health REAL,
                risk_health REAL,
                learning_health REAL,
                overall_status TEXT,
                alpha_status TEXT,
                execution_status TEXT,
                risk_status TEXT,
                learning_status TEXT,
                confidence TEXT,
                reason_summary TEXT
            )
        ''')
        conn.commit()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS edge_health_alert_state (
                alert_key TEXT PRIMARY KEY,
                last_sent_time TEXT,
                last_level TEXT
            )
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to init Health History DB: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def save_snapshot(metrics_dict: dict, db_path=DB_PATH):
    """
    Saves a snapshot of edge health to SQLite.
    metrics_dict should contain keys:
    overall_edge, alpha_health, execution_health, risk_health, learning_health
    overall_status, alpha_status, execution_status, risk_status, learning_status
    confidence, reason_summary
    """
    init_db(db_path)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Deduplication: prevent multiple saves in < 30s
        now = datetime.utcnow()
        cursor.execute("SELECT timestamp FROM edge_health_history ORDER BY timestamp DESC LIMIT 1")
        last_row = cursor.fetchone()
        if last_row:
            try:
                last_ts = datetime.fromisoformat(last_row[0])
                if (now - last_ts).total_seconds() < 30:
                    return  # Skip, too soon
            except Exception:
                pass
                
        # 90 days retention cleanup
        cutoff_90d = (now - timedelta(days=90)).isoformat()
        cursor.execute("DELETE FROM edge_health_history WHERE timestamp < ?", (cutoff_90d,))
                
        now_str = now.isoformat()
        cursor.execute('''
            INSERT INTO edge_health_history (
                timestamp, overall_edge, alpha_health, execution_health, risk_health, learning_health,
                overall_status, alpha_status, execution_status, risk_status, learning_status,
                confidence, reason_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            now_str,
            metrics_dict.get('overall_edge'),
            metrics_dict.get('alpha_health'),
            metrics_dict.get('execution_health'),
            metrics_dict.get('risk_health'),
            metrics_dict.get('learning_health'),
            metrics_dict.get('overall_status'),
            metrics_dict.get('alpha_status'),
            metrics_dict.get('execution_status'),
            metrics_dict.get('risk_status'),
            metrics_dict.get('learning_status'),
            metrics_dict.get('confidence'),
            metrics_dict.get('reason_summary')
        ))
        conn.commit()
        
        # Log structured event
        try:
            from gqos.common.structured_logger import log_structured_event
            log_structured_event(
                event_type="HEALTH_SNAPSHOT",
                decision_id=f"SYS-{now_str[-6:].replace(':', '').replace('.', '')}",
                symbol="SYSTEM",
                side="SYSTEM",
                status=metrics_dict.get('overall_status', 'UNKNOWN'),
                reason=metrics_dict.get('reason_summary', ''),
                metadata={"overall_edge": metrics_dict.get('overall_edge')}
            )
        except Exception:
            pass
            
        evaluate_alerts(metrics_dict, db_path)
            
    except Exception as e:
        logger.error(f"Failed to save Health History snapshot: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_history(hours=24, db_path=DB_PATH) -> pd.DataFrame:
    try:
        if not os.path.exists(db_path):
            return pd.DataFrame()
            
        conn = sqlite3.connect(db_path)
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        df = pd.read_sql_query('''
            SELECT * FROM edge_health_history
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        ''', conn, params=(cutoff,))
        
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        return df
    except Exception as e:
        logger.error(f"Failed to fetch health history: {e}")
        return pd.DataFrame()
    finally:
        if 'conn' in locals():
            conn.close()

def evaluate_alerts(latest: dict, db_path=DB_PATH):
    alerts = []
    
    # Base CRITICAL / WATCH limits
    dimensions = {
        'Alpha': latest.get('alpha_health'),
        'Execution': latest.get('execution_health'),
        'Risk': latest.get('risk_health'),
        'Learning': latest.get('learning_health'),
        'Overall': latest.get('overall_edge')
    }
    
    is_low_confidence = False
    if "LOW" in str(latest.get('confidence', '')).upper():
        is_low_confidence = True
        
    for name, score in dimensions.items():
        if score is None: continue
        
        if name == 'Risk' and score < 60:
            msg = f"Risk Health < 60 ({score:.1f}). Trading halt recommended."
            alerts.append({"level": "CRITICAL", "msg": msg})
            
        if score < 40:
            if is_low_confidence:
                alerts.append({"level": "WATCH", "msg": f"{name} Health < 40 ({score:.1f}) but confidence is LOW."})
            else:
                alerts.append({"level": "CRITICAL", "msg": f"{name} Health < 40 ({score:.1f})."})
        elif score < 60 and name != 'Risk':
            alerts.append({"level": "WATCH", "msg": f"{name} Health < 60 ({score:.1f})."})
            
    # Trend Analysis
    df_24h = get_history(hours=24, db_path=db_path)
    if not df_24h.empty and len(df_24h) >= 1:
        # Calculate 24h drop in Overall Edge
        oldest_overall = df_24h.iloc[0]['overall_edge']
        current_overall = latest.get('overall_edge')
        if oldest_overall is not None and current_overall is not None:
            if oldest_overall - current_overall > 15:
                alerts.append({"level": "WATCH", "msg": f"Overall Edge dropped > 15 pts in 24h (from {oldest_overall:.1f} to {current_overall:.1f})."})
                
        # Calculate Rolling Average drop for Execution Health
        if 'execution_health' in df_24h.columns:
            rolling_avg_exec = df_24h['execution_health'].mean()
            current_exec = latest.get('execution_health')
            if pd.notna(rolling_avg_exec) and current_exec is not None:
                if rolling_avg_exec - current_exec > 20:
                    alerts.append({"level": "WATCH", "msg": f"Execution Health dropped > 20 pts from recent average ({rolling_avg_exec:.1f} -> {current_exec:.1f})."})
    
    now = datetime.utcnow()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check and send recovery if everything is HEALTHY
        cursor.execute("SELECT alert_key, last_level FROM edge_health_alert_state WHERE last_level = 'CRITICAL'")
        active_criticals = cursor.fetchall()
        
        all_healthy = True
        for name, score in dimensions.items():
            if score is not None and score < 60:
                all_healthy = False
                break
                
        if all_healthy and active_criticals:
            for ac in active_criticals:
                alert_key = ac[0]
                cursor.execute("UPDATE edge_health_alert_state SET last_level = 'HEALTHY' WHERE alert_key = ?", (alert_key,))
                try:
                    from notifications.telegram_notifier import send_telegram
                    send_telegram(f"✅ HEALTH_RECOVERED: {alert_key} has stabilized.")
                except Exception as e:
                    logger.warning(f"Telegram recovery alert failed: {e}")
            conn.commit()
            
        for alert in alerts:
            alert_key = alert['msg'].split(' ')[0] # E.g. "Alpha", "Risk", "Overall"
            level = alert['level']
            
            # Check cooldown
            cursor.execute("SELECT last_sent_time, last_level FROM edge_health_alert_state WHERE alert_key = ?", (alert_key,))
            row = cursor.fetchone()
            
            should_send = False
            if row is None:
                should_send = True
            else:
                last_time = datetime.fromisoformat(row[0])
                last_level = row[1]
                
                # If level escalated, or > 30 mins passed
                if level == "CRITICAL" and last_level != "CRITICAL":
                    should_send = True
                elif (now - last_time).total_seconds() > (30 * 60): # 30 min cooldown
                    should_send = True
                    
            if should_send:
                cursor.execute('''
                    INSERT INTO edge_health_alert_state (alert_key, last_sent_time, last_level)
                    VALUES (?, ?, ?)
                    ON CONFLICT(alert_key) DO UPDATE SET last_sent_time=excluded.last_sent_time, last_level=excluded.last_level
                ''', (alert_key, now.isoformat(), level))
                conn.commit()
                
                # Send Telegram if CRITICAL
                if level == "CRITICAL":
                    try:
                        from notifications.telegram_notifier import send_telegram
                        send_telegram(f"🚨 CRITICAL EDGE DECAY: {alert['msg']}")
                    except Exception as e:
                        logger.warning(f"Telegram alert failed: {e}")
                        
                # Emit structured log
                try:
                    from gqos.common.structured_logger import log_structured_event
                    log_structured_event(
                        event_type="HEALTH_ALERT",
                        decision_id=f"SYS-{str(uuid.uuid4().hex[:8].upper())}",
                        symbol="SYSTEM",
                        side="SYSTEM",
                        status=level,
                        reason=alert['msg']
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error in evaluate_alerts: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
            
    return alerts
