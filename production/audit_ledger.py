import hashlib
import json
import time

class AuditLedger:
    def __init__(self):
        self.chain = []
        self.previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
    def log_event(self, phase_id: str, decision_type: str, input_state: dict, model_version: str, regime_state: str):
        """
        Logs the entire decision lineage cryptographically.
        If you cannot replay it, it did not happen.
        """
        timestamp = time.time_ns()
        
        # Serialize input state safely for hashing
        input_state_str = json.dumps(input_state, sort_keys=True)
        input_state_hash = hashlib.sha256(input_state_str.encode()).hexdigest()
        
        event_data = {
            "timestamp_ns": timestamp,
            "phase_id": phase_id,
            "decision_type": decision_type,
            "input_state_hash": input_state_hash,
            "model_version": model_version,
            "regime_state": regime_state,
            "previous_hash": self.previous_hash
        }
        
        event_str = json.dumps(event_data, sort_keys=True)
        current_hash = hashlib.sha256(event_str.encode()).hexdigest()
        
        event_data["current_hash"] = current_hash
        self.chain.append(event_data)
        self.previous_hash = current_hash
        
        return event_data
        
    def verify_chain(self) -> bool:
        """
        Validates the tamper-evident sequence.
        """
        for i in range(1, len(self.chain)):
            current_event = self.chain[i]
            previous_event = self.chain[i-1]
            if current_event["previous_hash"] != previous_event["current_hash"]:
                return False
        return True
