"""ml/predictor.py — XGBoost model loader and predictor."""
import os
import json
import hashlib
import logging
import joblib
import pandas as pd
from mlops.registry import registry

logger = logging.getLogger(__name__)


class MLPredictor:
    def __init__(self, fallback_model_path: str = "models/xgboost_model.pkl"):
        """Initialize Multi-Symbol Predictor"""
        self.fallback_model_path = fallback_model_path
        self._models = {} # dict of symbol -> {"model": model, "metadata": dict, "threshold": float, "version": str, "features": list}

    @property
    def threshold(self) -> float:
        if "FALLBACK" in self._models:
            return float(self._models["FALLBACK"].get("threshold", 0.5))
        return 0.5

    def reload(self):
        """Clear cached models so the next prediction loads the latest registry artifacts."""
        count = len(self._models)
        self._models.clear()
        logger.info("MLPredictor cache cleared; %s cached model(s) will be reloaded on demand.", count)
        return True
        
    def _load_model_for_symbol(self, symbol: str):
        """Loads the production model for a symbol from registry."""
        if symbol in self._models:
            return True
            
        model, metadata = registry.get_production_model(symbol)
        
        if model and metadata:
            self._models[symbol] = {
                "model": model,
                "metadata": metadata,
                "threshold": metadata.get("optimal_threshold", 0.5),
                "version": metadata.get("model_version", "unknown"),
                "features": metadata.get("features", [])
            }
            logger.info(f"Loaded Production ML model for {symbol}: {self._models[symbol]['version']} (threshold={self._models[symbol]['threshold']:.3f})")
            return True
            
        # Fallback for backward compatibility
        if os.path.exists(self.fallback_model_path) and "FALLBACK" not in self._models:
            try:
                data = joblib.load(self.fallback_model_path)
                file_mtime = os.path.getmtime(self.fallback_model_path)
                version = data.get("model_version", f"xgb_{int(file_mtime)}")
                self._models["FALLBACK"] = {
                    "model": data.get("model"),
                    "metadata": data,
                    "threshold": data.get("threshold", 0.5),
                    "version": version,
                    "features": data.get("feature_names", [])
                }
                logger.info(f"Loaded Fallback ML model: {version} (threshold={data.get('threshold', 0.5):.3f})")
            except Exception as e:
                logger.critical(f"Failed to load fallback ML model. Error: {e}")
                
        if symbol not in self._models and "FALLBACK" in self._models:
            self._models[symbol] = self._models["FALLBACK"]
            return True
            
        return False

    def predict(self, ml_features: dict, symbol: str = "UNKNOWN") -> dict:
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
            'model_version': "none",
            'hash': feature_hash
        }
        
        if not self._load_model_for_symbol(symbol):
            return result
            
        model_data = self._models[symbol]
        model = model_data["model"]
        threshold = model_data["threshold"]
        version = model_data["version"]
        expected_features = model_data["features"]
        
        result['model_version'] = version
            
        try:
            # Build feature vector in exact order of saved feature_names
            # Ensure all expected features are present; if not, fill with 0 or drop
            if expected_features:
                missing = [f for f in expected_features if f not in ml_features]
                if missing:
                    logger.warning(f"Missing features {missing} for {symbol}. Filling with 0.")
                    for m in missing:
                        ml_features[m] = 0.0
                
                # Reorder strictly according to model expectation
                df = pd.DataFrame([ml_features], columns=expected_features)
            else:
                df = pd.DataFrame([ml_features])
                
            prob = model.predict_proba(df)[0][1]  # Get probability for class 1
            result['probability'] = round(float(prob), 4)
            
            if prob >= threshold:
                result['approved'] = True
                result['reason'] = "approved"
            else:
                result['reason'] = f"prob={prob:.3f} < threshold={threshold:.3f}"
        except Exception as e:
            logger.error(f"Prediction error during inference: {e}")
            result['reason'] = f"prediction_error: {str(e)}"
            
        return result
