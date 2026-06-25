import os
import pandas as pd
import json
import time

class PatternCache:
    _instance = None

    def __new__(cls, db_path=None):
        if cls._instance is None:
            cls._instance = super(PatternCache, cls).__new__(cls)
            cls._instance.df = None
            cls._instance.loaded_at = None
            cls._instance.memory_usage_mb = 0.0
            if db_path:
                cls._instance.load(db_path)
        return cls._instance

    def load(self, db_path: str):
        if os.path.exists(db_path):
            self.df = pd.read_parquet(db_path)
            
            # Pre-parse json for fast filtering
            def parse_sig(x):
                try: return json.loads(x)
                except: return {}
            
            sigs = self.df['feature_signature'].apply(parse_sig)
            self.df['atr_bucket'] = sigs.apply(lambda x: x.get('atr_bucket', 'Unknown'))
            self.df['adx_bucket'] = sigs.apply(lambda x: x.get('adx_bucket', 'Unknown'))
            self.df['trend_bucket'] = sigs.apply(lambda x: x.get('trend_bucket', 'Unknown'))
            
            self.loaded_at = time.time()
            self.memory_usage_mb = self.df.memory_usage(deep=True).sum() / (1024 * 1024)
        else:
            self.df = pd.DataFrame()
            self.loaded_at = time.time()
            self.memory_usage_mb = 0.0

    def get_health(self):
        return {
            "loaded_patterns": len(self.df) if self.df is not None else 0,
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "loaded_at": self.loaded_at,
            "data_version": "1.0"
        }

    def filter_exact(self, **kwargs):
        if self.df is None or self.df.empty:
            return pd.DataFrame()
        q = self.df
        for k, v in kwargs.items():
            if k in q.columns:
                q = q[q[k] == v]
        return q
