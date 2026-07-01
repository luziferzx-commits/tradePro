import os
import json
import logging
from datetime import datetime, timedelta
import tempfile
import shutil

logger = logging.getLogger("PatternCooldown")

class PatternCooldownManager:
    """
    Manages pattern usage cooldowns to prevent spamming the same setup.
    Persists state to data/learning/pattern_cooldown.json via atomic writes.
    Self-heals only from real opened/closed trades, not approved-but-unfilled
    signals.
    """
    def __init__(self, cooldown_hours=2.0, state_file="data/learning/pattern_cooldown.json"):
        self.cooldown_hours = timedelta(hours=cooldown_hours)
        self.state_file = state_file
        self.last_approved = {}
        self.probe_registry = {}
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        
        self._load_state()
        self._self_heal()
        
    def set_probe(self, decision_id: str, is_probe: bool):
        if is_probe and decision_id:
            self.probe_registry[decision_id] = True
            
    def is_probe(self, decision_id: str) -> bool:
        if not decision_id: return False
        return self.probe_registry.pop(decision_id, False) # Pop to avoid memory leak

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for pid, ts_str in data.items():
                        self.last_approved[pid] = datetime.fromisoformat(ts_str)
                logger.info(f"Loaded {len(self.last_approved)} cooldown entries from {self.state_file}")
            except Exception as e:
                logger.error(f"Failed to load cooldown state: {e}")

    def _save_state(self):
        try:
            data = {pid: ts.isoformat() for pid, ts in self.last_approved.items()}
            # Atomic write
            temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(self.state_file))
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f)
            shutil.move(temp_path, self.state_file)
        except Exception as e:
            logger.error(f"Failed to save cooldown state: {e}")

    def _self_heal(self):
        """Recover cooldown from trades that actually opened or closed."""
        try:
            now = datetime.utcnow()
            recovered = {}
            for pid, ts in self._iter_verified_trade_patterns():
                if pid and (now - ts) < timedelta(hours=24):
                    recovered[pid] = max(recovered.get(pid, ts), ts)

            active_cutoff = now - self.cooldown_hours
            changed = False
            for pid, ts in list(self.last_approved.items()):
                if ts >= active_cutoff and pid not in recovered:
                    self.last_approved.pop(pid, None)
                    changed = True

            for pid, ts in recovered.items():
                if pid not in self.last_approved or ts > self.last_approved[pid]:
                    self.last_approved[pid] = ts
                    changed = True

            if changed:
                logger.info(f"Self-healed {len(recovered)} cooldown entries from verified trades")
                self._save_state()
        except Exception as e:
            logger.error(f"Failed self-heal from verified trades: {e}")

    def _iter_verified_trade_patterns(self):
        pending_file = "data/learning/pending_trades.json"
        if os.path.exists(pending_file):
            with open(pending_file, "r", encoding="utf-8") as f:
                pending = json.load(f)
            for meta in pending.values():
                if not isinstance(meta, dict) or not meta.get("ticket"):
                    continue
                ts = self._parse_ts(meta.get("open_time"))
                if ts:
                    yield meta.get("pattern_id"), ts

        outcomes_file = "data/learning/live_outcomes.jsonl"
        if os.path.exists(outcomes_file):
            with open(outcomes_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = self._parse_ts(record.get("open_time") or record.get("close_time"))
                    if ts:
                        yield record.get("pattern_id"), ts

    def _parse_ts(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None

    def check_cooldown(self, pattern_id: str) -> bool:
        """Returns True if the pattern is in cooldown (rejected), False otherwise (approved to proceed)."""
        if not pattern_id:
            return False
            
        now = datetime.utcnow()
        if pattern_id in self.last_approved:
            last_ts = self.last_approved[pattern_id]
            if (now - last_ts) < self.cooldown_hours:
                return True # STILL IN COOLDOWN
                
        return False
        
    def record_approval(self, pattern_id: str):
        """Record the approval of a pattern."""
        if pattern_id:
            self.last_approved[pattern_id] = datetime.utcnow()
            self._save_state()

cooldown_manager = PatternCooldownManager()
