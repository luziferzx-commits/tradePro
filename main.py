import time
import logging
from datetime import datetime, timedelta
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.market_score import MarketScoreCalculator
from market.regime_detector import RegimeDetector
from news.economic_filter import EconomicFilter
from safety.circuit_breaker import CircuitBreaker
from ai.gemini_filter import GeminiFilter
from risk.manager import RiskManager
from execution.executor import Executor
from execution.shadow_executor import ShadowExecutor
from database.logger import DatabaseLogger
from database.repository import repository
from database.models import MarketState
from positions.tracker import PositionTracker
from features.feature_store import feature_store
from analytics.daily_report import daily_report
from analytics.decision_tree import decision_logger
from analytics.model_health_report import health_monitor
from ml.predictor import ml_predictor
import MetaTrader5 as mt5

import logging.handlers

# Configure built-in logging with Log Rotation
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.handlers.RotatingFileHandler(
            "goldbot.log", maxBytes=10*1024*1024, backupCount=5
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("GoldBot")

def main():
    logger.info("Initializing GoldBot V1...")
    
    if not mt5_client.connect():
        logger.error("Failed to start due to MT5 connection error.")
        return

    news_filter = EconomicFilter()
    # Legacy strategy removed from flow, using Scorer V2
    # strategy = PrimarySignalGenerator()
    ai_filter = GeminiFilter()
    
    last_candle_time = None

    try:
        while True:
            # 1. Sync Positions
            PositionTracker.sync_open_positions()

            # 2. Fetch Data (500 candles to allow 200-EMA & rolling calc stability)
            df = mt5_client.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, 500)
            if df is None or df.empty:
                time.sleep(10)
                continue

            current_candle_time = df['time'].iloc[-1]
            
            # 3. Check if new candle closed
            if last_candle_time is None or current_candle_time > last_candle_time:
                
                # Check DB to prevent duplicate trades on restarts
                with repository.get_session() as session:
                    existing_state = session.query(MarketState).filter(
                        MarketState.timestamp == current_candle_time, 
                        MarketState.symbol == settings.SYMBOL, 
                        MarketState.timeframe == settings.TIMEFRAME
                    ).first()
                    
                    if existing_state:
                        logger.info(f"Candle {current_candle_time} already processed in DB. Skipping.")
                        daily_report.log_block("duplicate")
                        last_candle_time = current_candle_time
                        time.sleep(10)
                        continue

                logger.info(f"New closed candle detected at {current_candle_time}")
                decision_logger.reset()
                last_candle_time = current_candle_time
                
                logger.info("1. MT5 data loaded.")
                
                # Calculate Indicators
                df = IndicatorCalculator.add_indicators(df)
                indicators = IndicatorCalculator.get_latest_indicators(df)
                logger.info("2. Indicator calculation completed.")
                decision_logger.log_step("Indicators", True)
                
                # Detect Regime
                regime = RegimeDetector.detect(df)
                logger.info(f"3. Market regime detected: {regime.get('trend_state', 'UNKNOWN')}")
                decision_logger.log_step("Market Regime", True)
                
                # 4. Generate Strategy Signal via MarketScoreCalculator
                market_score = MarketScoreCalculator.calculate(df, regime)
                final_dir = market_score['final_direction']
                final_score_val = market_score['final_score']
                
                # Store normalized features including scores for ML
                feature_store.store_features(
                    symbol=settings.SYMBOL,
                    timeframe=settings.TIMEFRAME,
                    features={
                        "timestamp": current_candle_time,
                        "close": df['close'].iloc[-1],
                        **indicators,
                        **regime,
                        **market_score
                    }
                )

                # Log Market State
                market_state = DatabaseLogger.log_market_state(
                    symbol=settings.SYMBOL,
                    timeframe=settings.TIMEFRAME,
                    close_price=df['close'].iloc[-1],
                    indicators=indicators,
                    regime=regime
                )
                
                logger.info("4. Quantitative Market Score calculated.")
                
                if final_dir == "NEUTRAL":
                    logger.info("5. No clear bias (NEUTRAL). Waiting next candle...")
                    decision_logger.log_step("Quant Score", False, f"Score too low ({final_score_val})")
                    decision_logger.print_tree(str(current_candle_time))
                    continue
                    
                logger.info(f"Quant Engine generated {final_dir} bias with score {final_score_val:.1f}")
                decision_logger.log_step("Quant Score", True, f"{final_dir} (Score: {final_score_val:.1f})")
                daily_report.log_signal()
                
                db_signal = DatabaseLogger.log_signal(
                    market_state_id=market_state.id,
                    strategy_name="V2_MultiScorer",
                    direction=final_dir,
                    market_score=market_score
                )
                
                # XGBoost ML Prediction
                logger.info("5. XGBoost Prediction started...")
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
                
                ml_result = ml_predictor.predict(ml_features)
                
                # 6. Market Memory Similarity
                from ml.market_memory import market_memory
                memory_sim = market_memory.get_similarity(ml_features)
                logger.info(f"Market Memory Similarity: {memory_sim:.2f}")
                decision_logger.log_step("Market Memory", True, f"Sim: {memory_sim:.2f}")
                
                with repository.get_session() as session:
                    sig = session.query(db_signal.__class__).get(db_signal.id)
                    sig.ml_probability = float(ml_result['probability'])
                    sig.ml_model_version = ml_result['model_version']
                    sig.ml_feature_hash = ml_result['feature_hash']
                    sig.ml_expected_rr = float(ml_result['expected_rr'])
                    sig.ml_expected_holding_time = float(ml_result['expected_holding_time_hrs'])
                    sig.ml_expected_drawdown = float(ml_result['expected_max_dd_r'])
                    sig.ml_rejected = not ml_result['approved']
                    sig.ml_rejection_reason = ml_result['reason']
                    session.commit()
                
                if not ml_result['approved']:
                    logger.info(f"5. ML rejected trade: {ml_result['reason']} (Prob: {ml_result['probability']:.3f})")
                    decision_logger.log_step("ML Predictor", False, f"Rejected: {ml_result['reason']}")
                    decision_logger.print_tree(str(current_candle_time))
                    continue
                    
                decision_logger.log_step("ML Predictor", True, f"Prob: {ml_result['probability']:.3f}")
                
                # 6. Safety & News Check
                if not CircuitBreaker.check_all(settings.SYMBOL):
                    logger.warning("6. Trade blocked by Circuit Breaker.")
                    decision_logger.log_step("Safety Checks", False, "Circuit Breaker Active")
                    decision_logger.print_tree(str(current_candle_time))
                    daily_report.log_block("safety")
                    continue
                    
                if not news_filter.is_safe_to_trade():
                    logger.warning("7. Trade blocked by Economic News Filter.")
                    decision_logger.log_step("News Filter", False, "High Impact News")
                    decision_logger.print_tree(str(current_candle_time))
                    daily_report.log_block("news")
                    continue
                
                decision_logger.log_step("Safety & News", True)

                # 7. Consensus Check (Quant + ML + Memory)
                # Gemini removed in V6.1
                decision_logger.log_step("Consensus Engine", True, "Quant+ML Match")

                # 8. Execution
                logger.info("8. Risk manager decision started...")
                sl_points = 500
                
                # Fetch latest health score
                health_score = health_monitor.get_latest_health()
                
                volume = RiskManager.calculate_position_size(
                    symbol=settings.SYMBOL, 
                    sl_points=sl_points,
                    ml_prob=ml_result['probability'],
                    memory_sim=memory_sim,
                    health_score=health_score
                )
                
                if volume <= 0:
                    logger.error("Calculated volume is 0 or invalid. Execution blocked.")
                    decision_logger.log_step("Risk Manager", False, "Calculated volume is 0")
                    decision_logger.print_tree(str(current_candle_time))
                    continue
                    
                decision_logger.log_step("Risk Manager", True)
                    
                acc_info = mt5.account_info()
                est_risk = (acc_info.balance * settings.RISK_PER_TRADE_PCT) if acc_info else 0.0
                daily_report.log_intended_execution(final_dir, volume, est_risk)
                
                logger.info("11. Order execution started...")
                if settings.SHADOW_MODE:
                    logger.info(f"SHADOW_MODE Execution {final_dir} with volume {volume}")
                    decision_logger.log_step("Shadow Execution", True, f"{final_dir} {volume} lots")
                    ShadowExecutor.execute_trade(
                        signal_id=db_signal.id,
                        symbol=settings.SYMBOL,
                        direction=final_dir,
                        volume=volume,
                        sl_points=sl_points
                    )
                elif settings.DRY_RUN:
                    logger.info(f"DRY_RUN Execution {final_dir} with volume {volume}")
                    decision_logger.log_step("Execution", True, f"DRY_RUN {final_dir} {volume} lots")
                else:
                    logger.info(f"Executing {final_dir} with volume {volume}")
                    decision_logger.log_step("Execution", True, f"{final_dir} {volume} lots")
                    Executor.execute_trade(
                        signal_id=db_signal.id,
                        symbol=settings.SYMBOL,
                        direction=final_dir,
                        volume=volume,
                        sl_points=sl_points
                    )
                
                decision_logger.print_tree(str(current_candle_time))
            
            logger.info("12. Waiting for next candle...")
            # Sleep before checking again
            time.sleep(30)
            
    except KeyboardInterrupt:
        logger.info("GoldBot stopped by user.")
    finally:
        mt5_client.disconnect()

if __name__ == "__main__":
    main()
