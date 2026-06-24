"""ml/predictor.py — XGBoost model loader and predictor."""
import os
import json
import hashlib
import logging
import joblib
import pandas as pd

logger = logging.getLogger(__name__)


class MLPredictor:
    def __init__(self, model_path: str = "models/xgboost_model.pkl"):
        """Initialize and lazily load the XGBoost model."""
        self.model_path = model_path
        self._available = False
        self.model = None
        self.feature_names = []
        self.threshold = 0.5
        self.model_version = "unknown"
        
        self._load_model()
        
    def _load_model(self):
        """Loads the saved joblib dictionary from disk."""
        if not os.path.exists(self.model_path):
            logger.critical(f"ML Model file missing at {self.model_path}. Predictor will deny all trades.")
            self._available = False
            return
            
        try:
            data = joblib.load(self.model_path)
            self.model = data.get("model")
            self.feature_names = data.get("feature_names", [])
            self.threshold = data.get("threshold", 0.5)
            # Default to file modification time if version not explicitly set
            file_mtime = os.path.getmtime(self.model_path)
            self.model_version = data.get("model_version", f"xgb_{int(file_mtime)}")
            
            self._available = True
            logger.info(f"Loaded ML model: {self.model_version} (threshold={self.threshold:.3f})")
            
        except Exception as e:
            logger.critical(f"Failed to load ML model from {self.model_path}. Error: {e}")
            self._available = False

    def predict(self, ml_features: dict) -> dict:
        """
        Executes prediction on the feature dictionary.
        Returns a dict adhering to the strict contract expected by main.py.
        """
        # Hash features for auditing (sort keys to ensure deterministic hash)
        feats_json = json.dumps(ml_features, sort_keys=True)
        feature_hash = hashlib.md5(feats_json.encode('utf-8')).hexdigest()[:8]
        
        # Base result
        result = {
            'probability': 0.0,
            'approved': False,
            'reason': "model_not_loaded",
            'model_version': self.model_version,
            'feature_hash': feature_hash,
            'expected_rr': 2.0,
            'expected_holding_time_hrs': 4.0,
            'expected_max_dd_r': 0.5
        }
        
        if not self._available or not self.model:
            return result
            
        try:
            # Build feature vector in exact order of saved feature_names
            X_list = [ml_features.get(feat, 0.0) for feat in self.feature_names]
            X_df = pd.DataFrame([X_list], columns=self.feature_names)
            
            # Predict probability of class 1 (win)
            prob = float(self.model.predict_proba(X_df)[0][1])
            approved = (prob >= self.threshold)
            
            result['probability'] = prob
            result['approved'] = approved
            
            if approved:
                result['reason'] = "approved"
            else:
                result['reason'] = f"prob={prob:.3f} < threshold={self.threshold:.3f}"
                
        except Exception as e:
            logger.error(f"Prediction error during inference: {e}")
            result['reason'] = f"prediction_error: {str(e)}"
            
        return result
