import time
import logging
import yaml
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

logger = logging.getLogger("GoldBot.Scanner")

class MarketScanner:
    def __init__(self, config_path="config/symbols.yaml"):
        self.config_path = config_path
        self.symbols_config = self.load_config()
        self.last_candle_times = {}
        self.scan_count = 0
        
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
            
            # Check Spread
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"[Scanner] Failed to get symbol info for {symbol}")
                continue
                
            if not symbol_info.visible:
                mt5.symbol_select(symbol, True)
                symbol_info = mt5.symbol_info(symbol)
                
            spread = symbol_info.spread
            max_spread = cfg.get("max_spread", 50)
            if spread > max_spread:
                pipeline_stats.log_reject("spread_too_high", symbol)
                logger.warning(f"[Scanner] {symbol} skipped: spread too high ({spread} > {max_spread})")
                continue
                
            timeframe = cfg.get("timeframe", "M5")
            df = mt5_client.get_historical_data(symbol, timeframe, 500)
            if df is None or df.empty:
                logger.warning(f"[Scanner] Failed to get data for {symbol}")
                continue
                
            current_candle_time = df['time'].iloc[-1]
            last_time = self.last_candle_times.get(symbol)
            
            # Only process closed candles (new candle detected)
            if last_time is not None and current_candle_time <= last_time:
                continue
                
            self.last_candle_times[symbol] = current_candle_time
            pipeline_stats.log_pass("candles_checked")
            
            df = IndicatorCalculator.add_indicators(df)
            indicators = IndicatorCalculator.get_latest_indicators(df)
            pipeline_stats.log_pass("indicators_pass")
            
            regime = RegimeDetector.detect(df)
            pipeline_stats.log_pass("regime_pass")
            
            # We need market_type for session score
            market_type = cfg.get("market_type", "metal")
            
            market_score = MarketScoreCalculator.calculate(df, regime)
            final_dir = market_score['final_direction']
            
            if final_dir == "NEUTRAL":
                pipeline_stats.log_reject("quant_neutral", symbol)
                continue
                
            pipeline_stats.log_pass("quant_pass")
                
            recent_high = df.iloc[-3]['recent_high_20'] if len(df) > 2 else df['high'].iloc[-1]
            recent_low = df.iloc[-3]['recent_low_20'] if len(df) > 2 else df['low'].iloc[-1]
            rh_dist = (recent_high - df['close'].iloc[-1]) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            rl_dist = (df['close'].iloc[-1] - recent_low) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            
            # We need market_type for session score
            market_type = cfg.get("market_type", "metal")
            
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
            
            if not ml_result['approved']:
                reason = ml_result['reason']
                prob = ml_result['probability']
                pipeline_stats.log_ml_probability(prob)
                
                if "No production model" in reason or "skipped" in reason:
                    pipeline_stats.log_reject("ml_model_not_found", symbol)
                else:
                    pipeline_stats.log_reject("ml_probability_too_low", symbol)
                
                logger.info(f"[Scanner] {symbol} rejected by ML: {reason}")
                
                # Request 4: Log ML reject details
                if "Top Factors" in reason:
                    req_conf = cfg.get("min_confidence", 0.55)
                    logger.info(f"[ML Detail] Required Conf: {req_conf}. {reason}")
                continue
                
            prob = ml_result['probability']
            pipeline_stats.log_ml_probability(prob)
            min_conf = cfg.get("min_confidence", 0.55)
            if prob < min_conf:
                pipeline_stats.log_reject("ml_probability_too_low", symbol)
                logger.info(f"[Scanner] {symbol} rejected: probability {prob:.3f} < {min_conf}")
                continue
                
            pipeline_stats.log_pass("ml_pass")
            logger.info(f"[Scanner] Signal {symbol} {final_dir} confidence={prob:.3f}")
            
            memory_sim = market_memory.get_similarity(symbol, ml_features)
            # We don't have a strict memory_sim reject threshold right now, but let's say it passes
            pipeline_stats.log_pass("memory_pass")
            
            valid_signals.append({
                "symbol": symbol,
                "direction": final_dir,
                "probability": prob,
                "similarity": memory_sim,
                "config": cfg,
                "features": ml_features,
                "timestamp": current_candle_time,
                "score": market_score
            })
            
        # Sort by probability + similarity
        valid_signals.sort(key=lambda x: (x["probability"] + (x["similarity"] * 0.5)), reverse=True)
        
        self.scan_count += 1
        if self.scan_count % 10 == 0:
            # Note: With M5 and 1 minute intervals, 10 scans = 10 minutes, which is roughly 2 candles.
            # But the user asked for every 10 candles or 30 minutes. 
            # If scan interval is 60s, 30 minutes is 30 scans.
            pass
            
        if self.scan_count % 30 == 0:
            pipeline_stats.print_summary("XAUUSDm")
            
        return valid_signals

market_scanner = MarketScanner()
