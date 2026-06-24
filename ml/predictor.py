import pandas as pd
import hashlib
import json
from mlops.registry import registry
import logging

logger = logging.getLogger("GoldBot.MLPredictor")

class MLPredictor:
    def __init__(self):
        self.models = {}
        self.metadatas = {}
        
    def get_model(self, symbol):
        if symbol in self.models:
            return self.models[symbol], self.metadatas[symbol]
            
        from config.settings import settings
        
        model, metadata = registry.get_production_model(symbol)
        if model is None:
            # Check if generic fallback is allowed
            allow_generic = settings.MULTI_MARKET.get("allow_generic_model_fallback", False)
            
            # Special case for Gold: historically XAUUSD was the only model, so it can use generic
            if allow_generic or "XAU" in symbol:
                model, metadata = registry.get_production_model(None)
                if model is None:
                    logger.warning(f"No production model found for {symbol} and no generic fallback.")
                    return None, None
                else:
                    logger.info(f"[ML] {symbol} model loaded successfully (fallback to generic XAUUSD model).")
            else:
                logger.warning(f"[ML] {symbol} skipped: symbol-specific model not found, NO_TRADE. Generic model disabled for safety.")
                return None, None
        else:
            logger.info(f"[ML] {symbol} model loaded successfully (symbol-specific).")
                
        self.models[symbol] = model
        self.metadatas[symbol] = metadata
        return model, metadata
            
    def predict(self, symbol, features_dict):
        model, metadata = self.get_model(symbol)
        if model is None:
            return {
                "approved": False,
                "reason": f"No production model loaded for {symbol}.",
                "probability": 0.0,
                "feature_hash": "N/A"
            }
            
        expected_features = metadata.get("features", [])
        
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
        is_drifted, drift_reason = drift_detector.check_drift(features_dict, metadata)
        if is_drifted:
            return {
                "approved": False,
                "reason": drift_reason,
                "probability": 0.0,
                "feature_hash": feature_hash,
                "model_version": metadata.get("model_version", "unknown")
            }
        
        try:
            import xgboost as xgb
            prob = model.predict_proba(df)[0][1]
            
            # XAI: Explainable AI
            contribs = model.get_booster().predict(xgb.DMatrix(df), pred_contribs=True)[0]
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
                "model_version": metadata.get("model_version", "unknown")
            }
            
        approved = prob >= 0.55
        
        return {
            "approved": approved,
            "probability": prob,
            "feature_hash": feature_hash,
            "model_version": metadata.get("model_version", "unknown"),
            "expected_rr": metadata.get("expected_rr", 2.5),
            "expected_holding_time_hrs": metadata.get("expected_holding_time_hrs", 4.0),
            "expected_max_dd_r": metadata.get("expected_max_dd_r", 10.0),
            "reason": xai_reason
        }

ml_predictor = MLPredictor()
