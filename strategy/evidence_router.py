import logging
import os
from config.settings import settings
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
        
        # Load symbol-specific thresholds
        import yaml
        symbols_path = os.path.join(base_dir, 'config', 'symbols.yaml')
        self.symbol_config = {}
        if os.path.exists(symbols_path):
            with open(symbols_path, 'r') as f:
                config = yaml.safe_load(f)
                self.symbol_config = config.get('symbols', {})

    def evaluate(self, df_live, symbol: str, decision_id: str = None, log_events: bool = True):
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
        
        long_match = self.similarity_engine.find_similar_patterns(live_features, "LONG", threshold=0.70)
        short_match = self.similarity_engine.find_similar_patterns(live_features, "SHORT", threshold=0.70)
        
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
        
        logger.info(
            f"🔍 [EVIDENCE DEBUG] {symbol} "
            f"Best Match: {best_direction} | "
            f"Sim: {best_match['similarity_score']:.2f} | "
            f"PF: {best_match['aggregate_pf']:.2f} | "
            f"ExpR: {best_match['aggregate_expectancy_r']:.3f} | "
            f"N: {best_match['sample_size']} | "
            f"Promo: {best_promo}"
        )
        
        # 1. EMIT SIGNAL_EVALUATED
        if log_events:
            try:
                from gqos.common.structured_logger import log_structured_event
                log_structured_event(
                    event_type="SIGNAL_EVALUATED",
                    decision_id=decision_id or "UNKNOWN",
                    symbol=symbol,
                    side=best_direction,
                    status="EVALUATED",
                    reason="Starting evaluation",
                    metadata={
                        "similarity": float(best_match.get('similarity_score', 0)),
                        "profit_factor": float(best_match.get('aggregate_pf', 0)),
                        "expectancy_r": float(best_match.get('aggregate_expectancy_r', 0)),
                        "promotion_status": best_promo,
                        "pattern_id": best_match.get('nearest_pattern', {}).get('pattern_id', '') if isinstance(best_match.get('nearest_pattern'), dict) else str(best_match.get('nearest_pattern', ''))
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log SIGNAL_EVALUATED: {e}")
        
        # Decision Tree Tracking
        decision_tree = []
        
        # Helper to log rejection and return
        def reject_signal(reason: str, tree: list):
            tree.append(f"FAIL {reason} ✗")
            if log_events:
                try:
                    from gqos.common.structured_logger import log_structured_event
                    log_structured_event(
                        event_type="SIGNAL_REJECTED",
                        decision_id=decision_id or "UNKNOWN",
                        symbol=symbol,
                        side=best_direction,
                        status="REJECTED",
                        reason=reason,
                        metadata={
                            "decision_tree": tree,
                            "similarity": float(best_match.get('similarity_score', 0)),
                            "profit_factor": float(best_match.get('aggregate_pf', 0)),
                            "expectancy_r": float(best_match.get('aggregate_expectancy_r', 0)),
                            "promotion_status": best_promo,
                            "pattern_id": best_match.get('nearest_pattern', {}).get('pattern_id', '') if isinstance(best_match.get('nearest_pattern'), dict) else str(best_match.get('nearest_pattern', ''))
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log SIGNAL_REJECTED: {e}")
            return None
            
        # Hard Rejection Rules
        sim_score = best_match['similarity_score']
        if sim_score < 0.70:
            return reject_signal(f"Similarity Low ({sim_score:.2f} < 0.70)", decision_tree)
        decision_tree.append(f"PASS Similarity ({sim_score:.2f}) ✓")
            
        sample_size = best_match['sample_size']
        if sample_size < 50: 
            return reject_signal(f"Sample Size Low ({sample_size} < 50)", decision_tree)
        decision_tree.append(f"PASS Sample Size ({sample_size}) ✓")
            
        pf = best_match['aggregate_pf']
        
        # PROBE Tier Logic
        is_probe = False
        clean_symbol = symbol.replace("m", "") # Remove 'm' suffix if any
        sym_data = self.symbol_config.get(clean_symbol, {})
        target_pf = float(sym_data.get('min_profit_factor', 1.10))
        sim_rec = None
        try:
            from gqos.learning.simulation_analyzer import load_recommendation
            sim_rec = load_recommendation(clean_symbol, best_direction)
            if sim_rec:
                target_pf = max(0.90, target_pf + float(sim_rec.get("pf_threshold_adjust", 0.0) or 0.0))
                decision_tree.append(
                    f"INFO SimRec {sim_rec.get('action')} PFadj={float(sim_rec.get('pf_threshold_adjust', 0.0) or 0.0):+.3f} "
                    f"AvgR={float(sim_rec.get('avg_r', 0.0) or 0.0):+.2f} N={int(sim_rec.get('samples', 0) or 0)}"
                )
        except Exception as e:
            logger.debug(f"[SimulationAnalyzer] recommendation skipped for {symbol}: {e}")
        
        probe_whitelist = {"EURUSD", "XAUUSD", "XAGUSD", "GER40"}
        if clean_symbol in probe_whitelist and (target_pf - 0.07) <= pf < target_pf:
            is_probe = True
            decision_tree.append(f"PASS Profit Factor PROBE ({pf:.2f}) ✓")
        elif pf < target_pf: 
            return reject_signal(f"Profit Factor Low ({pf:.2f} < {target_pf:.2f})", decision_tree)
        else:
            decision_tree.append(f"PASS Profit Factor ({pf:.2f}) ✓")
            
        expr = best_match['aggregate_expectancy_r']
        min_expectancy = float(settings.MIN_EVIDENCE_EXPECTANCY_R)
        if sim_rec:
            min_expectancy = max(-0.02, min_expectancy + float(sim_rec.get("expectancy_threshold_adjust", 0.0) or 0.0))
        if expr < min_expectancy:
            return reject_signal(f"Expectancy R Low ({expr:.2f} < {min_expectancy:.2f})", decision_tree)
        decision_tree.append(f"PASS ExpR ({expr:.2f}) ✓")
        
        # If no valid promotion in the whole candidate group, reject it
        if best_promo == 'REJECTED':
            return reject_signal(f"Promotion Blocked (REJECTED)", decision_tree)
            
        if is_probe:
            best_promo = 'PROBE'
            
        # Temporarily allow RESEARCH level patterns to trade on the Demo account
        if self.mode == "LIVE" and best_promo not in ['SHADOW_PASSED', 'LIVE_APPROVED', 'RESEARCH_VALIDATED', 'RESEARCH_DISCOVERED', 'PROBE']:
            return reject_signal(f"Promotion Policy ({best_promo} not allowed in LIVE)", decision_tree)
        decision_tree.append(f"PASS Promotion ({best_promo}) ✓")
        
        # Check pattern cooldown for every approved tier. Historical PF can be
        # stale during a live regime shift, so repeated approvals of the same
        # setup must cool down even when the pattern is not merely PROBE.
        from strategy.cooldown_manager import cooldown_manager
        nearest_pattern_id = best_match.get('nearest_pattern', {}).get('pattern_id', '') if isinstance(best_match.get('nearest_pattern'), dict) else str(best_match.get('nearest_pattern', ''))
        
        if cooldown_manager.check_cooldown(nearest_pattern_id):
            return reject_signal(f"Pattern Cooldown (Wait 6h)", decision_tree)
        decision_tree.append(f"PASS Cooldown ✓")
            
        # --- Apply COT Analysis ---
        try:
            from strategy.cot_analyzer import COTAnalyzer
            cot_data = COTAnalyzer.get_net_position(symbol)
            if cot_data:
                # If hedge funds are Bullish and we are Long -> boost confidence
                if cot_data['direction'] == "BULLISH" and best_direction == "LONG":
                    best_match['evidence_score'] = min(0.99, best_match['evidence_score'] * 1.2)
                    decision_tree.append(f"PASS COT Align (BULLISH) ✓")
                    logger.info(f"📈 [COT Boost] {symbol} LONG aligns with Hedge Funds (Net: {cot_data['net_position']})")
                elif cot_data['direction'] == "BEARISH" and best_direction == "SHORT":
                    best_match['evidence_score'] = min(0.99, best_match['evidence_score'] * 1.2)
                    decision_tree.append(f"PASS COT Align (BEARISH) ✓")
                    logger.info(f"📉 [COT Boost] {symbol} SHORT aligns with Hedge Funds (Net: {cot_data['net_position']})")
                else:
                    decision_tree.append(f"WARN COT Diverge ✓")
                    best_match['evidence_score'] = best_match['evidence_score'] * 0.8
                    logger.info(f"⚠️ [COT Conflict] {symbol} {best_direction} conflicts with Hedge Funds ({cot_data['direction']})")
        except Exception as e:
            logger.debug(f"[COT] Skipped for {symbol}: {e}")
        # --------------------------

        res = {
            "symbol": symbol,
            "direction": best_direction,
            "strategy": "EVIDENCE_ROUTER",
            "confidence": best_match['evidence_score'],
            "tp_mult": 1.5,
            "sl_mult": 1.0,
            "horizon": nearest['horizon'],
            "metadata": {
                "pattern_id": nearest['pattern_id'],
                "similarity": best_match['similarity_score'],
                "profit_factor": best_match['aggregate_pf'],
                "expectancy_r": best_match['aggregate_expectancy_r'],
                "occurrences": best_match['sample_size'],
                "decision_tree": decision_tree,
                "promotion_status": best_promo
            }
        }
        
        if is_probe:
            res['metadata']['PROBE_MODE'] = True
            
        return res
