import logging
import os
from research.universal_feature_store import UniversalFeatureStore
from research.query_engine import QueryEngine
from research.similarity_engine import SimilarityEngine
from market.session_detector import SessionDetector

logger = logging.getLogger("EvidenceRouter")

class EvidenceRouter:
    def __init__(self, base_dir, mode="SHADOW"):
        logger.info(f"Initializing Evidence Router in {mode} mode...")
        self.query_engine = QueryEngine(os.path.join(base_dir, 'data', 'pattern_store', 'pattern_database.parquet'))
        self.similarity_engine = SimilarityEngine(self.query_engine)
        self.mode = mode

    def evaluate(self, df_live, symbol: str):
        if df_live.empty or len(df_live) < 1:
            return None
            
        latest = df_live.iloc[-1]
        
        df_features = UniversalFeatureStore.extract_features(df_live, symbol, "M15")
        if df_features.empty:
            return None
            
        current_state = df_features.iloc[-1]
        
        def get_regime(row):
            if row['ema50'] > row['ema200'] and row['adx'] > 25: return "TREND"
            if row['ema50'] < row['ema200'] and row['adx'] > 25: return "TREND"
            return "RANGE"
            
        live_features = {
            "symbol": symbol,
            "session_label": SessionDetector.detect(latest['time'].timestamp()),
            "regime": get_regime(current_state),
            "atr_bucket": str(current_state['atr_bucket']),
            "adx_bucket": str(current_state['adx_bucket']),
            "trend_bucket": str(current_state['trend_bucket'])
        }
        
        long_match = self.similarity_engine.find_similar_patterns(live_features, "LONG", threshold=0.0) # lower to 0.0 just to see what we get
        short_match = self.similarity_engine.find_similar_patterns(live_features, "SHORT", threshold=0.0)
        
        candidates = []
        if long_match: candidates.append(("LONG", long_match))
        if short_match: candidates.append(("SHORT", short_match))
        
        if not candidates:
            logger.debug(f"[EvidenceRouter] {symbol} No candidates found at all.")
            return None
            
        # Rank by evidence score
        candidates.sort(key=lambda x: x[1]['evidence_score'], reverse=True)
        best_direction, best_match = candidates[0]
        
        nearest = best_match['nearest_pattern']
        
        # Use the highest promotion status in the candidate group instead of just the nearest
        valid_promos = [p for p in best_match.get('promotions', []) if p in ['RESEARCH_VALIDATED', 'RESEARCH_DISCOVERED']]
        best_promo = valid_promos[0] if valid_promos else 'REJECTED'
        
        logger.info(f"🔍 [EVIDENCE DEBUG] {symbol} Best Match: {best_direction} | Sim: {best_match['similarity_score']:.2f} | PF: {best_match['aggregate_pf']:.2f} | N: {best_match['sample_size']} | Promo: {best_promo}")
        
        # Hard Rejection Rules
        if best_match['similarity_score'] < 0.70:
            return None
        if best_match['sample_size'] < 50: 
            return None
        if best_match['aggregate_pf'] < 1.20: 
            return None
        if best_match['aggregate_expectancy_r'] <= 0: 
            return None
        
        # If no valid promotion in the whole candidate group, reject it
        if best_promo == 'REJECTED':
            return None
            
        # Temporarily allow RESEARCH level patterns to trade on the Demo account
        if self.mode == "LIVE" and best_promo not in ['SHADOW_PASSED', 'LIVE_APPROVED', 'RESEARCH_VALIDATED', 'RESEARCH_DISCOVERED']:
            return None
            
        return {
            "symbol": symbol,
            "direction": best_direction,
            "strategy": "EVIDENCE_ROUTER",
            "confidence": best_match['evidence_score'],
            "tp_mult": 1.5,
            "sl_mult": 1.0,
            "horizon": nearest['horizon'],
            "metadata": {
                "pattern_id": nearest['pattern_id'],
                "similarity_score": best_match['similarity_score'],
                "historical_pf": best_match['aggregate_pf'],
                "occurrences": best_match['sample_size']
            }
        }
