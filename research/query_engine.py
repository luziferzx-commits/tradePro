import os
import pandas as pd
from research.pattern_cache import PatternCache

class QueryEngine:
    def __init__(self, db_path: str):
        self.cache = PatternCache(db_path)

    def find_best_patterns(self, symbol=None, session=None, direction=None, min_pf=None, min_occurrences=None):
        df = self.cache.df
        if df is None or df.empty: return pd.DataFrame()
        
        q = df.copy()
        if symbol: q = q[q['symbol'] == symbol]
        if session: q = q[q['session_label'] == session]
        if direction: q = q[q['direction'] == direction]
        if min_pf is not None: q = q[q['profit_factor'] >= min_pf]
        if min_occurrences is not None: q = q[q['occurrences'] >= min_occurrences]
        
        return q.sort_values(by=['profit_factor', 'occurrences'], ascending=[False, False])

    def get_symbol_session_rules(self, symbol: str, session: str):
        return self.find_best_patterns(symbol=symbol, session=session, min_pf=1.2, min_occurrences=50)

    def get_pattern_by_id(self, pattern_id: str):
        df = self.cache.df
        if df is None or df.empty: return None
        res = df[df['pattern_id'] == pattern_id]
        return res.iloc[0].to_dict() if not res.empty else None

    def get_blacklisted_patterns(self, symbol: str, session: str):
        df = self.cache.df
        if df is None or df.empty: return pd.DataFrame()
        q = df[(df['symbol'] == symbol) & (df['session_label'] == session) & (df['occurrences'] >= 50) & (df['profit_factor'] < 1.0)]
        return q.sort_values(by='profit_factor', ascending=True)

    def get_coverage_stats(self, symbol: str, session: str, regime: str):
        df = self.cache.df
        if df is None or df.empty: return {}
        q = df[(df['symbol'] == symbol) & (df['session_label'] == session) & (df['regime'] == regime)]
        if q.empty: return {"explored_cells": 0, "well_known": 0, "blind_spots": 0}
        
        # Unique feature signatures
        cells = q.drop_duplicates(subset=['pattern_hash'])
        well_known = cells[cells['occurrences'] >= 50]
        blind_spots = cells[cells['occurrences'] < 50]
        
        return {
            "explored_cells": len(cells),
            "well_known": len(well_known),
            "blind_spots": len(blind_spots),
            "total_occurrences": cells['occurrences'].sum()
        }
