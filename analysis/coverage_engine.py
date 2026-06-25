import pandas as pd
from research.query_engine import QueryEngine

class CoverageEngine:
    def __init__(self, query_engine):
        self.qe = query_engine

    def assess_cell_status(self, row):
        n = row['occurrences']
        pf = row['profit_factor']
        
        if n < 50:
            return "BLIND_SPOT"
        elif pf < 1.0 and n >= 50:
            return "BLACKLISTED"
        elif n >= 100 and pf >= 1.2 and row['expectancy_r'] > 0:
            return "VALIDATED"
        else:
            return "RESEARCH_READY"

    def analyze_coverage(self):
        df = self.qe.cache.df
        if df is None or df.empty:
            return pd.DataFrame()
            
        df_eval = df.copy()
        df_eval['status'] = df_eval.apply(self.assess_cell_status, axis=1)
        return df_eval[['symbol', 'session_label', 'regime', 'direction', 'atr_bucket', 'adx_bucket', 'trend_bucket', 'occurrences', 'status', 'profit_factor']]

    def get_summary(self):
        df = self.analyze_coverage()
        if df.empty: return {}
        
        summary = df['status'].value_counts().to_dict()
        summary['Total Cells'] = len(df)
        return summary
