import time
import logging
import yaml
import os
import MetaTrader5 as mt5
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.market_score import MarketScoreCalculator
from market.regime_detector import RegimeDetector
from strategy.scorer import MultiScorer
from features.feature_store import feature_store
from ml.predictor import ml_predictor
from ml.market_memory import market_memory
from analytics.pipeline_stats import pipeline_stats
from logs.explainability import explainability_logger
from risk.session_health import AdaptiveSessionHealth

logger = logging.getLogger("GoldBot.Scanner")

class MarketScanner:
    def __init__(self, config_path="config/symbols.yaml"):
        self.config_path = config_path
        self.symbols_config = self.load_config()
        self.last_candle_times = {}
        self.scan_count = 0
        
        # Load Frozen V2.1 Config
        config_health_path = 'config/session_health.v2_1.yaml'
        if os.path.exists(config_health_path):
            try:
                with open(config_health_path, 'r') as f:
                    hp = yaml.safe_load(f)
                self.health_monitor = AdaptiveSessionHealth(
                    rolling_window=hp.get('rolling_window', 15),
                    recovery_trades=hp.get('recovery_trades', 5),
                    disabled_threshold=hp.get('disabled_threshold', 0.50),
                    degraded_multiplier=hp.get('degraded_multiplier', 0.60),
                    warning_multiplier=hp.get('warning_multiplier', 0.85)
                )
                logger.info(f"[Scanner] Loaded AdaptiveSessionHealth V2.1: {hp}")
            except Exception as e:
                logger.error(f"[Scanner] Failed to load {config_health_path}: {e}")
                self.health_monitor = AdaptiveSessionHealth()
        else:
            logger.warning("[Scanner] config/session_health.v2_1.yaml not found. Using defaults.")
            self.health_monitor = AdaptiveSessionHealth()
        
    def load_config(self):
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load {self.config_path}: {e}")
            return {}
            
    def get_active_symbols(self):
        active = {}
        for sym, cfg in self.symbols_config.items():
            if cfg.get("enabled", False):
                mtype = cfg.get("market_type", "")
                if mtype == "crypto" and not settings.MULTI_MARKET["allow_crypto"]: continue
                if mtype == "indices" and not settings.MULTI_MARKET["allow_indices"]: continue
                if mtype == "forex" and not settings.MULTI_MARKET["allow_forex"]: continue
                if mtype == "metal" and not settings.MULTI_MARKET["allow_metals"]: continue
                if mtype == "oil" and not settings.MULTI_MARKET["allow_oil"]: continue
                active[sym] = cfg
        return active

    def scan_markets(self):
        active_symbols = self.get_active_symbols()
        logger.info(f"[Scanner] Scanning {len(active_symbols)} active symbols...")
        
        valid_signals = []
        
        for symbol, cfg in active_symbols.items():
            logger.info(f"[Scanner] Checking {symbol}")
            
            # Default values for explainability logging
            ex_session = "UNKNOWN"
            ex_regime = "UNKNOWN"
            ex_market_score = 0.0
            ex_ml_prob = 0.0
            ex_prod_prob = 0.0
            ex_cand_prob = 0.0
            ex_gap_abs = 0.0
            ex_gap_signed = 0.0
            ex_session_health = "HEALTHY" # Because of A1 default
            ex_risk_mult = 1.0
            
            def log_explainability(decision, decision_stage, reasons):
                explainability_logger.log_signal(
                    symbol=symbol,
                    session=ex_session,
                    regime=ex_regime,
                    market_score=ex_market_score,
                    ml_probability=ex_ml_prob,
                    prod_probability=ex_prod_prob,
                    candidate_probability=ex_cand_prob,
                    probability_gap_abs=ex_gap_abs,
                    probability_gap_signed=ex_gap_signed,
                    session_health=ex_session_health,
                    risk_multiplier=ex_risk_mult,
                    health_dynamic=False,
                    health_source="initialized_default",
                    health_note="PnL feedback loop not implemented in A1",
                    decision=decision,
                    decision_stage=decision_stage,
                    reasons=reasons
                )
            
            # Check Spread
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"[Scanner] Failed to get symbol info for {symbol}")
                log_explainability("REJECT", "missing_data", ["missing_data"])
                continue
                
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
                symbol_info = mt5.symbol_info(symbol)
                
            spread = symbol_info.spread
            max_spread = cfg.get("max_spread", 50)
            if spread > max_spread:
                pipeline_stats.log_reject("spread_too_high", symbol)
                logger.warning(f"[Scanner] {symbol} skipped: spread too high ({spread} > {max_spread})")
                log_explainability("REJECT", "spread_filter", [f"spread_filter ({spread} > {max_spread})"])
                continue
                
            timeframe = cfg.get("timeframe", "M5")
            df = mt5_client.get_historical_data(symbol, timeframe, 500)
            if df is None or df.empty:
                logger.warning(f"[Scanner] Failed to get data for {symbol}")
                log_explainability("REJECT", "missing_data", ["missing_data"])
                continue
                
            current_candle_time = df['time'].iloc[-1]
            last_time = self.last_candle_times.get(symbol)
            
            # Only process closed candles (new candle detected)
            if last_time is not None and current_candle_time <= last_time:
                # Do not log explainability here to avoid spamming the same candle every second
                continue
                
            self.last_candle_times[symbol] = current_candle_time
            pipeline_stats.log_pass("candles_checked")
            
            df = IndicatorCalculator.add_indicators(df)
            indicators = IndicatorCalculator.get_latest_indicators(df)
            pipeline_stats.log_pass("indicators_pass")
            
            regime = RegimeDetector.detect(df)
            pipeline_stats.log_pass("regime_pass")
            ex_regime = regime.get('trend_state', 'UNKNOWN')
            
            market_type = cfg.get("market_type", "metal")
            
            # Get session for explainability
            def _get_session_name(hour: int, mtype: str) -> str:
                if mtype in ["metal", "forex"]:
                    if 7 <= hour < 13: return "London"
                    elif 13 <= hour < 21: return "NY"
                    else: return "Asia"
                return "NORMAL"
                
            ex_session = _get_session_name(current_candle_time.hour, market_type)
            
            market_score = MarketScoreCalculator.calculate(df, regime)
            final_dir = market_score['final_direction']
            ex_market_score = market_score['final_score']
            
            if final_dir == "NEUTRAL":
                pipeline_stats.log_reject("quant_neutral", symbol)
                log_explainability("REJECT", "market_score_filter", ["market_score_neutral"])
                continue
                
            pipeline_stats.log_pass("quant_pass")
                
            recent_high = df.iloc[-3]['recent_high_20'] if len(df) > 2 else df['high'].iloc[-1]
            recent_low = df.iloc[-3]['recent_low_20'] if len(df) > 2 else df['low'].iloc[-1]
            rh_dist = (recent_high - df['close'].iloc[-1]) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            rl_dist = (df['close'].iloc[-1] - recent_low) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            
            ml_features = {
                "final_score": market_score['final_score'],
                "trend_score": MultiScorer.get_trend_score(df, regime),
                "breakout_score": MultiScorer.get_breakout_score(df),
                "reversal_score": MultiScorer.get_reversal_score(df),
                "session_score": MultiScorer.get_session_score(current_candle_time, market_type),
                "atr": indicators['atr'],
                "atr_pct": (indicators['atr'] / df['close'].iloc[-1] * 100) if df['close'].iloc[-1] > 0 else 0,
                "adx": indicators['adx'],
                "ema50_slope": indicators['ema50_slope'],
                "rsi": indicators['rsi'],
                "macd": indicators['macd'],
                "hour_utc": current_candle_time.hour,
                "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
                "is_buy": 1 if final_dir == "BUY" else 0,
                "recent_high_20_distance": rh_dist,
                "recent_low_20_distance": rl_dist,
                "recent_high_20_distance_pct": (recent_high - df['close'].iloc[-1]) / df['close'].iloc[-1] * 100 if df['close'].iloc[-1] > 0 else 0,
                "recent_low_20_distance_pct": (df['close'].iloc[-1] - recent_low) / df['close'].iloc[-1] * 100 if df['close'].iloc[-1] > 0 else 0
            }
            
            # Use dynamic predictor
            ml_result = ml_predictor.predict(symbol, ml_features)
            
            ex_prod_prob = ml_result.get("prod_probability", 0.0)
            ex_cand_prob = ml_result.get("candidate_probability", 0.0)
            ex_gap_abs = abs(ex_prod_prob - ex_cand_prob)
            ex_gap_signed = ex_cand_prob - ex_prod_prob
            
            if not ml_result['approved']:
                reason = ml_result['reason']
                prob = ml_result['probability']
                ex_ml_prob = prob
                pipeline_stats.log_ml_probability(prob)
                
                if "No production model" in reason or "skipped" in reason:
                    pipeline_stats.log_reject("ml_model_not_found", symbol)
                    log_explainability("REJECT", "ml_filter", ["ml_model_not_found"])
                else:
                    pipeline_stats.log_reject("ml_probability_too_low", symbol)
                    log_explainability("REJECT", "ml_filter", [f"ml_threshold ({prob:.3f})"])
                
                logger.info(f"[Scanner] {symbol} rejected by ML: {reason}")
                
                if "Top Factors" in reason:
                    req_conf = cfg.get("min_confidence", 0.55)
                    logger.info(f"[ML Detail] Required Conf: {req_conf}. {reason}")
                continue
                
            prob = ml_result['probability']
            ex_ml_prob = prob
            pipeline_stats.log_ml_probability(prob)
            min_conf = cfg.get("min_confidence", 0.55)
            if prob < min_conf:
                pipeline_stats.log_reject("ml_probability_too_low", symbol)
                logger.info(f"[Scanner] {symbol} rejected: probability {prob:.3f} < {min_conf}")
                log_explainability("REJECT", "ml_filter", [f"ml_threshold ({prob:.3f} < {min_conf})"])
                continue
                
            pipeline_stats.log_pass("ml_pass")
            logger.info(f"[Scanner] Signal {symbol} {final_dir} confidence={prob:.3f}")
            
            memory_sim = market_memory.get_similarity(symbol, ml_features)
            pipeline_stats.log_pass("memory_pass")
            
            # --- Candidate V2.1 Adaptive Risk Layer ---
            features_for_health = {
                'symbol': symbol,
                'session': ex_session,
                'market_regime': ex_regime,
                'direction': final_dir
            }
            # Calculate Risk Multiplier
            ex_risk_mult = self.health_monitor.get_risk_multiplier(features_for_health)
            
            # Fetch the actual state of the Session+Regime tracker
            tracker = self.health_monitor._get_tracker(f"{ex_session} + {ex_regime}", "session_regime")
            if tracker:
                ex_session_health = tracker.state.name
            
            if ex_risk_mult == 0.0:
                log_explainability("REJECT", "session_health", ["session_health (DISABLED)"])
                continue
                
            # If we reach here, the signal is accepted
            log_explainability("ACCEPT", "accepted", [])
            
            valid_signals.append({
                "symbol": symbol,
                "direction": final_dir,
                "probability": prob,
                "similarity": memory_sim,
                "config": cfg,
                "features": ml_features,
                "timestamp": current_candle_time,
                "score": market_score,
                "risk_multiplier": ex_risk_mult,
                "session_health": ex_session_health
            })
            
        # Sort by probability + similarity
        valid_signals.sort(key=lambda x: (x["probability"] + (x["similarity"] * 0.5)), reverse=True)
        
        self.scan_count += 1
        if self.scan_count % 30 == 0:
            pipeline_stats.print_summary("XAUUSDm")
            
        return valid_signals

market_scanner = MarketScanner()
