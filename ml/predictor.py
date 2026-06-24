import pandas as pd
import hashlib
import json
from mlops.registry import registry
import logging

logger = logging.getLogger("GoldBot.MLPredictor")

class MLPredictor:
    def __init__(self):
        self.prod_models = {}
        self.prod_metadatas = {}
        self.cand_models = {}
        self.cand_metadatas = {}
        
    def get_models(self, symbol):
        from config.settings import settings
        
        # Production
        if symbol not in self.prod_models:
            prod_model, prod_meta = registry.get_production_model(symbol)
            if prod_model is None:
                allow_generic = settings.MULTI_MARKET.get("allow_generic_model_fallback", False)
                if allow_generic or "XAU" in symbol:
                    prod_model, prod_meta = registry.get_production_model(None)
                    if prod_model:
                        logger.info(f"[ML] {symbol} prod model fallback to generic XAUUSD.")
            else:
                logger.info(f"[ML] {symbol} prod model loaded.")
            self.prod_models[symbol] = prod_model
            self.prod_metadatas[symbol] = prod_meta
            
        # Candidate
        if symbol not in self.cand_models:
            cand_model, cand_meta = registry.get_candidate_model(symbol)
            if cand_model:
                logger.info(f"[ML] {symbol} cand model loaded for Shadow Testing.")
            self.cand_models[symbol] = cand_model
            self.cand_metadatas[symbol] = cand_meta
            
        return self.prod_models[symbol], self.prod_metadatas[symbol], self.cand_models[symbol], self.cand_metadatas[symbol]

    def _infer(self, model, metadata, features_dict):
        if model is None:
            return None
            
        expected_features = metadata.get("features", [])
        missing = [f for f in expected_features if f not in features_dict]
        if missing:
            return None
            
        df = pd.DataFrame([features_dict])[expected_features]
        try:
            import xgboost as xgb
            prob = model.predict_proba(df)[0][1]
            return prob
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return None
            
    def predict(self, symbol, features_dict):
        prod_model, prod_meta, cand_model, cand_meta = self.get_models(symbol)
        
        from config.settings import settings
        import yaml
        
        # Load min_confidence from symbols.yaml
        min_conf = 0.55
        try:
            with open("config/symbols.yaml", "r") as f:
                sym_cfg = yaml.safe_load(f).get(symbol, {})
                min_conf = sym_cfg.get("min_confidence", 0.55)
        except:
            pass
            
        prod_prob = self._infer(prod_model, prod_meta, features_dict)
        cand_prob = self._infer(cand_model, cand_meta, features_dict)
        
        from analytics.pipeline_stats import pipeline_stats
        
        prod_approved = False
        cand_approved = False
        
        if prod_prob is not None:
            prod_approved = prod_prob >= min_conf
        if cand_prob is not None:
            cand_approved = cand_prob >= min_conf
            
        # Shadow Logging
        if prod_prob is not None or cand_prob is not None:
            p_str = f"Prod: {prod_prob:.3f} {'APPROVE' if prod_approved else 'REJECT'}" if prod_prob is not None else "Prod: N/A"
            c_str = f"Cand: {cand_prob:.3f} {'APPROVE' if cand_approved else 'REJECT'}" if cand_prob is not None else "Cand: N/A"
            logger.info(f"[Shadow] {symbol} | {p_str} | {c_str}")
            pipeline_stats.log_shadow(symbol, prod_approved, cand_approved, prod_prob, cand_prob)
            
        # Safety Rules
        feature_str = json.dumps(features_dict, sort_keys=True)
        feature_hash = hashlib.sha256(feature_str.encode()).hexdigest()[:16]
        
        use_candidate = False
        if settings.DRY_RUN:
            if cand_model is not None:
                use_candidate = True
        else:
            if cand_model is not None and prod_model is None:
                logger.error(f"[SAFETY] Live trading attempted with Candidate Model for {symbol}. BLOCKED.")
                use_candidate = False
                
        # Return result based on active model
        active_prob = cand_prob if use_candidate else prod_prob
        active_approved = cand_approved if use_candidate else prod_approved
        active_meta = cand_meta if use_candidate else prod_meta
        
        if active_prob is None:
            return {
                "approved": False,
                "reason": "Model inference failed or no model available.",
                "probability": 0.0,
                "feature_hash": "N/A"
            }
            
        return {
            "approved": active_approved,
            "probability": active_prob,
            "feature_hash": feature_hash,
            "model_version": active_meta.get("model_version", "unknown") if active_meta else "unknown",
            "expected_rr": active_meta.get("expected_rr", 2.5) if active_meta else 2.5,
            "reason": f"Active Model (Cand={use_candidate}) prob {active_prob:.3f}"
        }

ml_predictor = MLPredictor()
