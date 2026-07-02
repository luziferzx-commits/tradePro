import os
from datetime import datetime, timezone
import pandas as pd

class SessionDetector:
    # Default boundaries (UTC)
    DEFAULT_SESSIONS = {
        "ASIA": {"start": 0, "end": 7},
        "LONDON": {"start": 7, "end": 13}, # Excludes overlap
        "LONDON_NY_OVERLAP": {"start": 13, "end": 16},
        "NEW_YORK": {"start": 16, "end": 21},
        "OFF_SESSION": {"start": 21, "end": 24}
    }

    @staticmethod
    def _get_hour(timestamp: float) -> float:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.hour + (dt.minute / 60.0)

    @classmethod
    def detect(cls, timestamp: float) -> str:
        hour = cls._get_hour(timestamp)
        
        for session, bounds in cls.DEFAULT_SESSIONS.items():
            if bounds["start"] <= hour < bounds["end"]:
                return session
        
        return "OFF_SESSION"

    @classmethod
    def minutes_from_open(cls, timestamp: float, session_label: str) -> int:
        if session_label not in cls.DEFAULT_SESSIONS:
            return 0
        
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        hour_fraction = dt.hour + (dt.minute / 60.0)
        
        start_hour = cls.DEFAULT_SESSIONS[session_label]["start"]
        diff_hours = hour_fraction - start_hour
        
        if diff_hours < 0:
            diff_hours += 24 # Cross-midnight case (not present in our default but safe)
            
        return int(diff_hours * 60)

    @classmethod
    def analyze_session(cls, timestamp: float) -> dict:
        session = cls.detect(timestamp)
        mins = cls.minutes_from_open(timestamp, session)
        return {
            "session_label": session,
            "minutes_from_session_open": mins,
            "is_overlap_session": session == "LONDON_NY_OVERLAP"
        }
