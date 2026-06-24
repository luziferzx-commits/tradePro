import argparse
import logging
from datetime import datetime
import pandas as pd

from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.market_score import MarketScoreCalculator
from market.regime_detector import RegimeDetector
from ml.predictor import ml_predictor
from ai.gemini_filter import GeminiFilter
from analytics.decision_tree import decision_logger

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("GoldBot.Replay")

def run_replay(target_time_str, use_gemini):
    try:
        target_time = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        logger.error("Invalid time format. Use YYYY-MM-DD HH:MM")
        return
        
    logger.info(f"Replaying state at {target_time} (Gemini Live: {use_gemini})")
    
    if not mt5_client.connect():
        logger.error("Failed to connect to MT5.")
        return
        
    df = mt5_client.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, 500)
    if df is None or df.empty:
        logger.error("Failed to fetch historical data.")
        return
        
    df = df[df['time'] <= target_time].copy()
    if df.empty or df['time'].iloc[-1] != target_time:
        logger.warning(f"No exact candle found for {target_time}. Closest is {df['time'].iloc[-1] if not df.empty else 'None'}")
        
    decision_logger.reset()
    decision_logger.log_step("Data Fetch", True)
    
    df = IndicatorCalculator.add_indicators(df)
    indicators = IndicatorCalculator.get_latest_indicators(df)
    decision_logger.log_step("Indicators", True)
    
    regime = RegimeDetector.detect(df)
    decision_logger.log_step("Market Regime", True)
    
    market_score = MarketScoreCalculator.calculate(df, regime)
    final_dir = market_score['final_direction']
    final_score_val = market_score['final_score']
    
    if final_dir == "NEUTRAL":
        decision_logger.log_step("Quant Score", False, "NEUTRAL")
        decision_logger.print_tree(str(target_time))
        return
        
    decision_logger.log_step("Quant Score", True, f"{final_dir} (Score: {final_score_val:.1f})")
    
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
        "hour_utc": target_time.hour,
        "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
        "is_buy": 1 if final_dir == "BUY" else 0,
        "recent_high_20_distance": rh_dist,
        "recent_low_20_distance": rl_dist
    }
    
    ml_result = ml_predictor.predict(ml_features)
    if not ml_result['approved']:
        decision_logger.log_step("ML Predictor", False, f"Rejected: {ml_result['reason']} (Prob: {ml_result['probability']:.3f})")
        decision_logger.print_tree(str(target_time))
        return
        
    decision_logger.log_step("ML Predictor", True, f"Prob: {ml_result['probability']:.3f}")
    
    if use_gemini:
        ai_filter = GeminiFilter()
        ai_decision = ai_filter.evaluate_signal(settings.SYMBOL, market_score, regime, indicators)
        if not ai_decision['approve']:
            decision_logger.log_step("Gemini Review", False, ai_decision['reason'])
        else:
            decision_logger.log_step("Gemini Review", True, f"Confidence: {ai_decision['confidence']}")
    else:
        decision_logger.log_step("Gemini Review", True, "SKIPPED (Simulated)")
        
    decision_logger.print_tree(str(target_time))
    mt5_client.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GoldBot Replay Mode")
    parser.add_argument("timestamp", type=str, help="Timestamp in YYYY-MM-DD HH:MM format")
    parser.add_argument("--gemini-live", action="store_true", help="Call live Gemini API (consumes tokens)")
    args = parser.parse_args()
    
    run_replay(args.timestamp, args.gemini_live)
