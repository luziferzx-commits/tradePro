import logging
import json
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class FeatureStore:
    def __init__(self, data_dir="data/features"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            
    def store_features(self, symbol: str, timeframe: str, features: dict):
        """
        Stores a normalized dictionary of features for future ML pipelines.
        """
        try:
            filename = f"{self.data_dir}/{symbol}_{timeframe}_features.jsonl"
            
            # Ensure timestamp is string for JSON
            if 'timestamp' in features and isinstance(features['timestamp'], datetime):
                features['timestamp'] = features['timestamp'].isoformat()
            elif 'timestamp' not in features:
                features['timestamp'] = datetime.utcnow().isoformat()
                
            with open(filename, 'a') as f:
                f.write(json.dumps(features) + '\n')
        except Exception as e:
            logger.error(f"Failed to store features: {e}")

feature_store = FeatureStore()
