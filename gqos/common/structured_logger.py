import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger("StructuredLogger")

def log_structured_event(
    event_type: str, 
    decision_id: str, 
    symbol: str, 
    side: str, 
    status: str, 
    reason: str = "",
    metadata: Optional[dict] = None
):
    """
    Outputs a structured JSON log for external consumption (Grafana Loki, ELK, etc).
    Required schema: event_type, ts, decision_id, symbol, side, status, reason
    """
    payload = {
        "event_type": event_type,
        "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decision_id": decision_id,
        "symbol": symbol,
        "side": side,
        "status": status,
        "reason": reason
    }
    
    if metadata:
        payload.update(metadata)

    try:
        from gqos.learning.missed_opportunity_tracker import missed_opportunity_tracker
        missed_opportunity_tracker.on_event(payload)
    except Exception as e:
        logger.debug(f"Missed opportunity tracker skipped event: {e}")
        
    payload_json = json.dumps(payload)
    logger.info(payload_json)
    
    # Fail-safe append to JSONL
    try:
        events_file = os.getenv("GQOS_SYSTEM_EVENTS_FILE")
        if not events_file:
            # __file__ is structured_logger.py inside gqos/common
            # os.path.dirname(__file__) -> gqos/common
            # os.path.dirname(os.path.dirname(__file__)) -> gqos
            # then go one level up to GoldGpt root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            events_file = os.path.join(project_root, "data", "learning", "system_events.jsonl")
        os.makedirs(os.path.dirname(events_file), exist_ok=True)
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(payload_json + "\n")
    except Exception as e:
        logger.warning(f"Failed to append to system_events.jsonl: {e}")
