import json
import hashlib
from typing import Optional
from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope

class AuditLogWriter:
    def __init__(self, event_bus: IEventBus, filepath: str = "audit_log.jsonl"):
        self.filepath = filepath
        self._event_bus = event_bus
        self._last_hash = "0" * 64 # Genesis hash
        self._sequence = 0
        
        # Subscribe as a catch-all listener if bus supports it,
        # or we might need to modify bus.py or subscribe to specific events.
        # For simplicity, let's assume we can subscribe to all by tapping into bus internals
        # or the bus supports a wildcard / interceptor.
        
    def append(self, envelope: MessageEnvelope) -> MessageEnvelope:
        """
        Appends an event to the immutable log with a cryptographic hash chain.
        """
        event_type_name = type(envelope.payload).__name__
        # Filter out high-frequency noise
        if event_type_name in ["MarketDataEvent", "HeartbeatEvent"]:
            return envelope
            
        self._sequence += 1
        
        from decimal import Decimal
        from enum import Enum
        
        class AuditEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, Decimal):
                    return str(obj)
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return super().default(obj)
                
        log_entry = {
            "sequence": self._sequence,
            "message_id": envelope.message_id,
            "correlation_id": envelope.correlation_id,
            "trace_id": envelope.trace_id,
            "run_id": envelope.run_id,
            "timestamp": envelope.timestamp,
            "event_type": event_type_name,
            "payload": envelope.payload,
            "previous_hash": self._last_hash
        }
                
        # Calculate current hash
        entry_str = json.dumps(log_entry, sort_keys=True, cls=AuditEncoder)
        current_hash = hashlib.sha256(entry_str.encode('utf-8')).hexdigest()
        log_entry["hash"] = current_hash
        
        self._last_hash = current_hash
        
        # Append to file
        with open(self.filepath, 'a') as f:
            f.write(json.dumps(log_entry, cls=AuditEncoder) + "\n")
            
        return envelope
            
    def get_current_state_hash(self) -> str:
        return self._last_hash
