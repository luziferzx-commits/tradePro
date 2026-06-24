import time
import logging
import yaml
import MetaTrader5 as mt5
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.market_score import MarketScoreCalculator
from market.regime_detector import RegimeDetector
from features.feature_store import feature_store
from ml.predictor import ml_predictor
from ml.market_memory import market_memory

logger = logging.getLogger("GoldBot.Scanner")

class MarketScanner:
    def __init__(self, config_path="config/symbols.yaml"):
        self.config_path = config_path
        self.symbols_config = self.load_config()
        
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
                logger.warning(f"[Scanner] {symbol} skipped: spread too high ({spread} > {max_spread})")
                continue
                
            timeframe = cfg.get("timeframe", "M5")
            df = mt5_client.get_historical_data(symbol, timeframe, 500)
            if df is None or df.empty:
                logger.warning(f"[Scanner] Failed to get data for {symbol}")
                continue
                
            current_candle_time = df['time'].iloc[-1]
            
            df = IndicatorCalculator.add_indicators(df)
            indicators = IndicatorCalculator.get_latest_indicators(df)
            regime = RegimeDetector.detect(df)
            market_score = MarketScoreCalculator.calculate(df, regime)
            final_dir = market_score['final_direction']
            
            if final_dir == "NEUTRAL":
                continue
                
            recent_high = df.iloc[-3]['recent_high_20'] if len(df) > 2 else df['high'].iloc[-1]
            recent_low = df.iloc[-3]['recent_low_20'] if len(df) > 2 else df['low'].iloc[-1]
            rh_dist = (recent_high - df['close'].iloc[-1]) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            rl_dist = (df['close'].iloc[-1] - recent_low) / df['atr'].iloc[-1] if df['atr'].iloc[-1] > 0 else 0
            
            ml_features = {
                "final_score": market_score['final_score'],
                "trend_score": market_score.get('trend_score', 0),
                "breakout_score": market_score.get('breakout_score', 0),
                "reversal_score": market_score.get('reversal_score', 0),
                "session_score": market_score.get('session_score', 0),
                "atr": indicators['atr'],
                "adx": indicators['adx'],
                "ema50_slope": indicators['ema50_slope'],
                "rsi": indicators['rsi'],
                "macd": indicators['macd'],
                "hour_utc": current_candle_time.hour,
                "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
                "is_buy": 1 if final_dir == "BUY" else 0,
                "recent_high_20_distance": rh_dist,
                "recent_low_20_distance": rl_dist
            }
            
            # Use dynamic predictor
            ml_result = ml_predictor.predict(symbol, ml_features)
            
            if not ml_result['approved']:
                logger.info(f"[Scanner] {symbol} rejected by ML: {ml_result['reason']}")
                continue
                
            prob = ml_result['probability']
            min_conf = cfg.get("min_confidence", 0.55)
            if prob < min_conf:
                logger.info(f"[Scanner] {symbol} rejected: probability {prob:.3f} < {min_conf}")
                continue
                
            logger.info(f"[Scanner] Signal {symbol} {final_dir} confidence={prob:.3f}")
            
            memory_sim = market_memory.get_similarity(symbol, ml_features)
            
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
        return valid_signals

market_scanner = MarketScanner()
