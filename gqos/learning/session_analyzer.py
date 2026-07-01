import logging
import json
import os
from collections import defaultdict
from typing import Dict, List

logger = logging.getLogger("GQOS.SessionAnalyzer")

class SessionAnalyzer:
    """
    Dead Zone Analysis:
    Analyzes historical trade data by session to identify Dead Zones (WR < 40%).
    """

    def __init__(self, pending_trades_path: str = "data/learning/pending_trades.json"):
        self.pending_trades_path = pending_trades_path
        self.session_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'w': 0, 'l': 0})
        self._load_stats()

    def _load_stats(self):
        """
        Since MT5 history doesn't store session labels directly, we approximate 
        it based on time, or we can read from pending_trades if closed trades 
        are archived there. For now, we will compute session from time.
        """
        try:
            import os
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            if not mt5.initialize():
                return

            # Rolling history window instead of a hard-coded start date that has
            # to be bumped by hand. Override with GQOS_SESSION_LOOKBACK_DAYS.
            try:
                lookback_days = int(os.getenv("GQOS_SESSION_LOOKBACK_DAYS", "30"))
            except (TypeError, ValueError):
                lookback_days = 30
            start = datetime.now() - timedelta(days=max(1, lookback_days))
            deals = mt5.history_deals_get(start, datetime.now()) or []
            closed = [d for d in deals if d.entry == 1 and d.profit != 0]

            for d in closed:
                # Approximate session from deal time (UTC)
                dt = datetime.utcfromtimestamp(d.time)
                hour_utc = dt.hour
                
                if 7 <= hour_utc < 10: session = "London"
                elif 13 <= hour_utc < 16: session = "NY"
                elif 16 <= hour_utc < 24: session = "Asia_Early"
                elif 0 <= hour_utc < 4: session = "Asia_Late"
                elif 4 <= hour_utc < 7: session = "Dead_PreLondon"
                else: session = "Dead_Lunch"

                if d.profit > 0:
                    self.session_stats[session]['w'] += 1
                else:
                    self.session_stats[session]['l'] += 1
                    
            logger.info("SessionAnalyzer: Loaded stats from MT5 history.")
        except Exception as e:
            logger.error(f"SessionAnalyzer failed to load stats: {e}")

    def get_dead_zones(self) -> List[str]:
        """Returns a list of sessions that have WR < 40% with at least 5 trades."""
        dead_zones = []
        for session, s in self.session_stats.items():
            wins = s['w']
            losses = s['l']
            total = wins + losses
            if total >= 5:
                wr = wins / total
                if wr < 0.40:
                    dead_zones.append(session)
        
        # Dead_Lunch and Dead_PreLondon are always dead zones structurally
        for hardcoded in ["Dead_Lunch", "Dead_PreLondon"]:
            if hardcoded not in dead_zones:
                dead_zones.append(hardcoded)
                
        return dead_zones
        
    def is_dead_zone(self, session: str) -> bool:
        """Check if the current session is a dead zone."""
        return session in self.get_dead_zones()

session_analyzer = SessionAnalyzer()
