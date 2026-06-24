import pandas as pd
import hashlib
import json
from mlops.registry import registry
import logging

logger = logging.getLogger("GoldBot.MLPredictor")

class MLPredictor:
    def __init__(self):
        self.model, self.metadata = registry.get_production_model()
        if self.model is None:
            logger.warning("No production model found in registry.")
            
    def predict(self, features_dict):
        if self.model is None:
            return {
                "approved": False,
                "reason": "No production model loaded.",
                "probability": 0.0,
                "feature_hash": "N/A"
            }
            
        expected_features = self.metadata.get("features", [])
        
        # Check if all required features exist
        missing = [f for f in expected_features if f not in features_dict]
        if missing:
            return {
                "approved": False,
                "reason": f"Missing features: {missing}",
                "probability": 0.0,
                "feature_hash": "N/A"
            }
            
        # Build DataFrame in correct order
        df = pd.DataFrame([features_dict])[expected_features]
        
        # Hash features for tracking
        feature_str = json.dumps(df.iloc[0].to_dict(), sort_keys=True)
        feature_hash = hashlib.sha256(feature_str.encode()).hexdigest()[:16]
        
        # Check Drift
        from analytics.drift_detector import drift_detector
        is_drifted, drift_reason = drift_detector.check_drift(features_dict, self.metadata)
        if is_drifted:
            return {
                "approved": False,
                "reason": drift_reason,
                "probability": 0.0,
                "feature_hash": feature_hash,
                "model_version": self.metadata.get("model_version", "unknown")
            }
        
        try:
            import xgboost as xgb
            prob = self.model.predict_proba(df)[0][1]
            
            # XAI: Explainable AI
            contribs = self.model.get_booster().predict(xgb.DMatrix(df), pred_contribs=True)[0]
            feature_contribs = []
            for i, feat in enumerate(expected_features):
                if i < len(contribs) - 1:
                    feature_contribs.append((feat, contribs[i], features_dict[feat]))
                    
            # Sort by absolute contribution
            feature_contribs.sort(key=lambda x: abs(x[1]), reverse=True)
            top_factors = feature_contribs[:3]
            
            xai_reason = f"Probability {prob:.3f}. Top Factors:\n"
            for f, c, v in top_factors:
                sign = "+" if c > 0 else "-"
                xai_reason += f"{sign} {f} (Value: {v:.2f}) contributed {c:.3f}\n"
                
        except Exception as e:
            return {
                "approved": False,
                "reason": f"Model inference error: {str(e)}",
                "probability": 0.0,
                "feature_hash": feature_hash,
                "model_version": self.metadata.get("model_version", "unknown")
            }
            
        approved = prob >= 0.55
        
        return {
            "approved": approved,
            "probability": prob,
            "feature_hash": feature_hash,
            "model_version": self.metadata.get("model_version", "unknown"),
            "expected_rr": self.metadata.get("expected_rr", 2.5),
            "expected_holding_time_hrs": self.metadata.get("expected_holding_time_hrs", 4.0),
            "expected_max_dd_r": self.metadata.get("expected_max_dd_r", 10.0),
            "reason": xai_reason
        }

ml_predictor = MLPredictor()
