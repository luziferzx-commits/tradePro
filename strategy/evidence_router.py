import logging
import os
from config.settings import settings
from research.universal_feature_store import UniversalFeatureStore
from research.query_engine import QueryEngine
from research.similarity_engine import SimilarityEngine
from market.session_detector import SessionDetector

logger = logging.getLogger("EvidenceRouter")

class EvidenceRouter:
    def __init__(self, base_dir, mode="SHADOW", mt5_client=None):
        logger.info(f"Initializing Evidence Router in {mode} mode...")
        self.query_engine = QueryEngine(os.path.join(base_dir, 'data', 'pattern_store', 'pattern_database.parquet'))
        self.similarity_engine = SimilarityEngine(self.query_engine)
        self.mode = mode
        self.mt5_client = mt5_client
        
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
                        "similarity": float((best_match or {}).get('similarity_score', 0)),
                        "profit_factor": float((best_match or {}).get('aggregate_pf', 0)),
                        "expectancy_r": float((best_match or {}).get('aggregate_expectancy_r', 0)),
                        "promotion_status": best_promo,
                        "pattern_id": (best_match or {}).get('nearest_pattern', {}).get('pattern_id', '') if isinstance((best_match or {}).get('nearest_pattern'), dict) else str((best_match or {}).get('nearest_pattern', ''))
                    }
                )
            except Exception as e:
                logger.error(f"Failed to log SIGNAL_EVALUATED: {e}")
        
        # Decision Tree Tracking
        decision_tree = []
        pa_context = {}
        
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
                            "similarity": float((best_match or {}).get('similarity_score', 0)),
                            "profit_factor": float((best_match or {}).get('aggregate_pf', 0)),
                            "expectancy_r": float((best_match or {}).get('aggregate_expectancy_r', 0)),
                            "promotion_status": best_promo,
                            "pattern_id": (best_match or {}).get('nearest_pattern', {}).get('pattern_id', '') if isinstance((best_match or {}).get('nearest_pattern'), dict) else str((best_match or {}).get('nearest_pattern', '')),
                            "price_action_context": pa_context,
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log SIGNAL_REJECTED: {e}")
            return None

        def pa_action(category: str, default_action: str) -> str:
            try:
                from gqos.ops.pa_filter_calibrator import recommended_action
                action = recommended_action(category, default_action)
                if action in {"REJECT", "PENALTY", "IGNORE"}:
                    return action
            except Exception as e:
                logger.debug("PA calibration fallback for %s: %s", category, e)
            return str(default_action or "PENALTY").upper()

        def apply_pa_rule(category: str, default_action: str, penalty: float, reason: str) -> bool:
            action = pa_action(category, default_action)
            pa_context[f"{category.lower()}_action"] = action
            if action == "REJECT":
                return False
            if action == "IGNORE":
                decision_tree.append(f"INFO PA {category} ignored by calibration: {reason}")
                return True
            best_match['evidence_score'] *= penalty
            decision_tree.append(f"WARN {reason} penalty={penalty:.2f} action={action}")
            return True
            
        # Hard Rejection Rules
        sim_score = best_match['similarity_score']
        if sim_score < 0.70:
            return reject_signal(f"Similarity Low ({sim_score:.2f} < 0.70)", decision_tree)
        decision_tree.append(f"PASS Similarity ({sim_score:.2f}) ✓")
            
        sample_size = best_match['sample_size']
        if sample_size < 50: 
            return reject_signal(f"Sample Size Low ({sample_size} < 50)", decision_tree)
        decision_tree.append(f"PASS Sample Size ({sample_size}) ✓")
        
        # --- MTF & Price Action Context ---
        if self.mt5_client and getattr(settings, "ENABLE_ADVANCED_PRICE_ACTION_FILTERS", True):
            try:
                from strategy.price_action.mtf_analyzer import MTFAnalyzer
                from strategy.price_action.sr_detector import SRDetector
                from strategy.price_action.fvg_detector import FVGDetector
                from strategy.price_action.liquidity_detector import LiquidityDetector
                from strategy.price_action.divergence_detector import DivergenceDetector
                from strategy.price_action.institutional_filters import InstitutionalFilters
                
                # Fetch H4 Data
                df_h4 = self.mt5_client.get_h4_data(symbol, 200)
                # Fetch H1 Data
                df_h1 = self.mt5_client.get_historical_data(symbol, "H1", 200)
                df_d1 = self.mt5_client.get_historical_data(symbol, "D1", 5)
                
                if df_h4 is not None and df_h1 is not None:
                    current_price = float(latest['close'])
                    atr = float(current_state.get('atr', 0) or 0)

                    # 1. MTF Trend Check (H4)
                    h4_trend = MTFAnalyzer.evaluate_trend(df_h4)
                    pa_context["h4_trend"] = h4_trend
                    if h4_trend != "UNKNOWN" and h4_trend != "NEUTRAL":
                        h4_conflict = (
                            (best_direction == "LONG" and h4_trend == "BEARISH")
                            or (best_direction == "SHORT" and h4_trend == "BULLISH")
                        )
                        if h4_conflict:
                            action = pa_action("H4_TREND", settings.PA_H4_TREND_CONFLICT_ACTION)
                            pa_context["h4_trend_action"] = action
                            pa_context["h4_trend_conflict"] = True
                            if action == "REJECT":
                                return reject_signal(f"MTF H4 Trend Conflict ({h4_trend})", decision_tree)
                            if action == "PENALTY":
                                best_match['evidence_score'] *= settings.PA_TREND_CONFLICT_PENALTY
                                decision_tree.append(f"WARN MTF H4 Trend Conflict ({h4_trend}) penalty={settings.PA_TREND_CONFLICT_PENALTY:.2f} action={action}")
                            else:
                                decision_tree.append(f"INFO MTF H4 Trend Conflict ignored by calibration ({h4_trend})")
                        else:
                            decision_tree.append(f"PASS MTF H4 Align ({h4_trend})")

                    sweep = LiquidityDetector.detect_pdh_pdl_sweep(
                        latest,
                        LiquidityDetector.previous_daily_levels(df_d1),
                        buffer_atr=atr,
                    )
                    pa_context["liquidity_sweep"] = sweep.get("type")
                    if LiquidityDetector.conflicts_with_direction(best_direction, sweep):
                        action = pa_action("LIQUIDITY", settings.PA_LIQUIDITY_SWEEP_ACTION)
                        pa_context["liquidity_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"Liquidity Sweep Conflict ({sweep.get('type')})", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= 0.88
                            decision_tree.append(f"WARN Liquidity Sweep Conflict ({sweep.get('type')}) penalty=0.88 action={action}")
                        else:
                            decision_tree.append(f"INFO Liquidity Sweep Conflict ignored by calibration ({sweep.get('type')})")
                    elif sweep.get("type") != "NONE":
                        best_match['evidence_score'] = min(0.99, best_match['evidence_score'] * 1.05)
                        decision_tree.append(f"PASS Liquidity Sweep Supports ({sweep.get('type')})")

                    divergence = DivergenceDetector.detect_h4_divergence(df_h4)
                    pa_context["h4_divergence"] = divergence.get("type")
                    if DivergenceDetector.conflicts_with_direction(best_direction, divergence):
                        action = pa_action("DIVERGENCE", settings.PA_DIVERGENCE_ACTION)
                        pa_context["divergence_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"H4 Momentum Divergence Conflict ({divergence.get('type')})", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= 0.86
                            decision_tree.append(f"WARN H4 Divergence Conflict ({divergence.get('type')}) penalty=0.86 action={action}")
                        else:
                            decision_tree.append(f"INFO H4 Divergence Conflict ignored by calibration ({divergence.get('type')})")
                    elif divergence.get("type") != "NONE":
                        decision_tree.append(f"INFO H4 Divergence ({divergence.get('type')})")

                    # 2. S/R Zones Check (H4)
                    h4_zones = SRDetector.detect_zones(df_h4, window=15)
                    h4_sr_pct = max(0.0005, (atr * settings.PA_H4_SR_ATR_MULT / current_price) if atr > 0 else 0.0015)
                    is_h4_danger, h4_nearest, h4_dist = SRDetector.evaluate_sr_proximity(current_price, h4_zones, best_direction, min_distance_pct=h4_sr_pct)
                    pa_context["h4_sr_distance_pct"] = h4_dist if h4_dist != 999.0 else None
                    pa_context["h4_sr_nearest"] = h4_nearest or None
                    if is_h4_danger:
                        action = pa_action("H4_SR", settings.PA_H4_SR_ACTION)
                        pa_context["h4_sr_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"Hit H4 S/R Wall (Dist: {h4_dist*100:.2f}%)", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_H4_SR_PENALTY
                            decision_tree.append(f"WARN H4 S/R Wall (Dist: {h4_dist*100:.2f}%) penalty={settings.PA_H4_SR_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO H4 S/R Wall ignored by calibration (Dist: {h4_dist*100:.2f}%)")

                    # 3. S/R Zones Check (H1)
                    h1_zones = SRDetector.detect_zones(df_h1, window=15)
                    h1_sr_pct = max(0.0004, (atr * settings.PA_H1_SR_ATR_MULT / current_price) if atr > 0 else 0.0010)
                    is_h1_danger, h1_nearest, h1_dist = SRDetector.evaluate_sr_proximity(current_price, h1_zones, best_direction, min_distance_pct=h1_sr_pct)
                    pa_context["h1_sr_distance_pct"] = h1_dist if h1_dist != 999.0 else None
                    pa_context["h1_sr_nearest"] = h1_nearest or None
                    if is_h1_danger:
                        action = pa_action("H1_SR", "PENALTY")
                        pa_context["h1_sr_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"H1 S/R Proximity (Dist: {h1_dist*100:.2f}%)", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_H1_SR_PENALTY
                            decision_tree.append(f"WARN H1 S/R Proximity (Dist: {h1_dist*100:.2f}%) penalty={settings.PA_H1_SR_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO H1 S/R Proximity ignored by calibration (Dist: {h1_dist*100:.2f}%)")

                    # 4. FVG Alignment (H1)
                    h1_fvgs = FVGDetector.detect_recent_fvg(df_h1, lookback=30)
                    fvg_aligned = FVGDetector.get_fvg_alignment(best_direction, h1_fvgs, current_price, atr=atr)
                    pa_context["fvg_aligned"] = bool(fvg_aligned)
                    if fvg_aligned:
                        decision_tree.append("PASS FVG Smart Money Align")
                        best_match['evidence_score'] = min(0.99, best_match['evidence_score'] * settings.PA_FVG_BOOST)

                    chop = InstitutionalFilters.choppiness_index(df_h1)
                    pa_context["h1_chop"] = chop
                    if chop is not None and chop > settings.PA_CHOP_THRESHOLD and live_features.get("regime") == "TREND":
                        action = pa_action("CHOP", "PENALTY")
                        pa_context["chop_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"H1 CHOP High ({chop:.1f})", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_CHOP_TREND_PENALTY
                            decision_tree.append(f"WARN H1 CHOP High ({chop:.1f}) trend penalty={settings.PA_CHOP_TREND_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO H1 CHOP High ignored by calibration ({chop:.1f})")

                    volume_ctx = InstitutionalFilters.dry_breakout(df_live)
                    pa_context["dry_breakout"] = bool(volume_ctx.get("is_dry_breakout"))
                    pa_context["volume_ratio"] = volume_ctx.get("volume_ratio")
                    if volume_ctx.get("is_dry_breakout"):
                        action = pa_action("VOLUME", "PENALTY")
                        pa_context["volume_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"Dry Breakout Volume volRatio={float(volume_ctx.get('volume_ratio', 0.0)):.2f}", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_VOLUME_DRY_BREAKOUT_PENALTY
                            decision_tree.append(f"WARN Dry Breakout Volume volRatio={float(volume_ctx.get('volume_ratio', 0.0)):.2f} penalty={settings.PA_VOLUME_DRY_BREAKOUT_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO Dry Breakout Volume ignored by calibration volRatio={float(volume_ctx.get('volume_ratio', 0.0)):.2f}")

                    killzone = InstitutionalFilters.killzone_label(latest.get("time"))
                    pa_context["killzone"] = killzone
                    if live_features.get("regime") == "TREND" and not InstitutionalFilters.trend_following_allowed(killzone):
                        action = pa_action("KILLZONE", "PENALTY")
                        pa_context["killzone_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"Trend signal outside killzone ({killzone})", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_KILLZONE_OFFHOURS_PENALTY
                            decision_tree.append(f"WARN Trend signal outside killzone ({killzone}) penalty={settings.PA_KILLZONE_OFFHOURS_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO Trend signal outside killzone ignored by calibration ({killzone})")

                    usd_ctx = InstitutionalFilters.usd_basket_trend(self.mt5_client)
                    pa_context["usd_basket_trend"] = usd_ctx.get("trend")
                    pa_context["usd_basket_score"] = usd_ctx.get("score")
                    if InstitutionalFilters.usd_conflicts(symbol, best_direction, usd_ctx):
                        action = pa_action("USD", "PENALTY")
                        pa_context["usd_action"] = action
                        if action == "REJECT":
                            return reject_signal(f"USD Basket Conflict ({usd_ctx.get('trend')} score={float(usd_ctx.get('score', 0.0)):+.4f})", decision_tree)
                        if action == "PENALTY":
                            best_match['evidence_score'] *= settings.PA_USD_CONFLICT_PENALTY
                            decision_tree.append(f"WARN USD Basket Conflict ({usd_ctx.get('trend')} score={float(usd_ctx.get('score', 0.0)):+.4f}) penalty={settings.PA_USD_CONFLICT_PENALTY:.2f} action={action}")
                        else:
                            decision_tree.append(f"INFO USD Basket Conflict ignored by calibration ({usd_ctx.get('trend')} score={float(usd_ctx.get('score', 0.0)):+.4f})")
            except Exception as e:
                logger.error(f"Error evaluating MTF/Price Action: {e}")
        # ----------------------------------
            
        pf = best_match['aggregate_pf']

        # Overfit guard: patterns whose backtest PF is very high tend to be
        # curve-fit and fail live (analysis of live trades: research PF >= ~1.5
        # went 0% win rate, while the 1.1-1.3 band was profitable). Reject them
        # when a ceiling is configured (PATTERN_PF_CEILING, 0 = disabled).
        pf_ceiling = float(getattr(settings, "PATTERN_PF_CEILING", 0) or 0)
        if pf_ceiling > 0 and pf >= pf_ceiling:
            return reject_signal(
                f"Profit Factor overfit ({pf:.2f} >= ceiling {pf_ceiling:.2f})", decision_tree
            )

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
                sim_confidence = max(0.0, min(1.0, float(sim_rec.get("confidence", 0.0) or 0.0)))
                pf_adjust = float(sim_rec.get("pf_threshold_adjust", 0.0) or 0.0) * sim_confidence
                target_pf = max(0.90, target_pf + pf_adjust)
                decision_tree.append(
                    f"INFO SimRec {sim_rec.get('action')} {sim_rec.get('soft_rule', 'NEUTRAL')} "
                    f"Conf={sim_confidence:.2f} PFadj={pf_adjust:+.3f} "
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
            sim_confidence = max(0.0, min(1.0, float(sim_rec.get("confidence", 0.0) or 0.0)))
            min_expectancy = max(
                -0.02,
                min_expectancy + (float(sim_rec.get("expectancy_threshold_adjust", 0.0) or 0.0) * sim_confidence)
            )
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
                "session_label": live_features.get("session_label"),
                "regime": live_features.get("regime"),
                "atr_bucket": live_features.get("atr_bucket"),
                "decision_tree": decision_tree,
                "promotion_status": best_promo,
                "price_action_context": pa_context,
                "pa_h4_trend": pa_context.get("h4_trend"),
                "pa_h4_divergence": pa_context.get("h4_divergence"),
                "pa_liquidity_sweep": pa_context.get("liquidity_sweep"),
                "pa_fvg_aligned": pa_context.get("fvg_aligned"),
                "pa_h1_chop": pa_context.get("h1_chop"),
                "pa_killzone": pa_context.get("killzone"),
                "pa_usd_basket_trend": pa_context.get("usd_basket_trend"),
            }
        }
        if sim_rec:
            res["metadata"]["simulation_recommendation"] = {
                "action": sim_rec.get("action"),
                "soft_rule": sim_rec.get("soft_rule"),
                "confidence": sim_rec.get("confidence"),
                "avg_r": sim_rec.get("avg_r"),
                "win_rate": sim_rec.get("win_rate"),
                "samples": sim_rec.get("samples"),
            }
        
        if is_probe:
            res['metadata']['PROBE_MODE'] = True
            
        return res
