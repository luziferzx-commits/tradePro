import time
import logging
from datetime import datetime
from config.settings import settings
# Force DRY RUN globally as requested by user
settings.DRY_RUN = True

from data.mt5_client import mt5_client
from news.economic_filter import EconomicFilter
from safety.circuit_breaker import CircuitBreaker
from risk.manager import RiskManager
from risk.portfolio_manager import portfolio_manager
from execution.executor import Executor
from execution.shadow_executor import ShadowExecutor
from database.logger import DatabaseLogger
from positions.tracker import PositionTracker
from analytics.daily_report import daily_report
from analytics.decision_tree import decision_logger
from analytics.model_health_report import health_monitor
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
    logger.info("Initializing GoldBot Multi-Market V2...")
    logger.warning("FORCED DRY_RUN MODE ACTIVE. No real orders will be sent.")
    
    if not mt5_client.connect():
        logger.error("Failed to start due to MT5 connection error.")
        return

    from notifications.telegram_notifier import notify_bot_started
    notify_bot_started()

    news_filter = EconomicFilter()
    
    from market.scanner import market_scanner
    from analytics.pipeline_stats import pipeline_stats

    try:
        while True:
            # 1. Sync Positions
            PositionTracker.sync_open_positions()

            # 2. Multi-Market Scan
            valid_signals = market_scanner.scan_markets()
            
            logger.info(f"Scan complete. Found {len(valid_signals)} valid signals.")
            
            # 3. Process Signals (Highest Priority First)
            for signal_data in valid_signals:
                symbol = signal_data['symbol']
                direction = signal_data['direction']
                prob = signal_data['probability']
                sim = signal_data['similarity']
                cfg = signal_data['config']
                features = signal_data['features']
                market_score = signal_data['score']
                current_candle_time = signal_data['timestamp']
                
                logger.info(f"Processing {direction} signal for {symbol} (Prob: {prob:.3f}, Sim: {sim:.2f})")
                decision_logger.reset()
                
                # Check Circuit Breakers
                if not CircuitBreaker.check_all(symbol):
                    pipeline_stats.log_reject("circuit_breaker", symbol)
                    logger.warning(f"Trade blocked for {symbol} by Circuit Breaker.")
                    decision_logger.log_step("Safety Checks", False, "Circuit Breaker Active")
                    continue
                    
                if not news_filter.is_safe_to_trade():
                    pipeline_stats.log_reject("news_filter", symbol)
                    logger.warning(f"Trade blocked for {symbol} by Economic News Filter.")
                    decision_logger.log_step("News Filter", False, "High Impact News")
                    continue

                # Calculate Risk / Lots
                sl_points = cfg.get("atr_multiplier_sl", 1.5) * features['atr'] * 10 # Example conversion
                # Safety fallback
                if sl_points < 100: sl_points = 500
                
                health_score = health_monitor.get_latest_health()
                
                volume = RiskManager.calculate_position_size(
                    symbol=symbol, 
                    sl_points=sl_points,
                    ml_prob=prob,
                    memory_sim=sim,
                    health_score=health_score
                )
                
                # Apply risk multiplier per symbol config
                volume = volume * cfg.get("risk_multiplier", 1.0)
                
                if volume <= 0:
                    pipeline_stats.log_reject("order_validation_failed", symbol)
                    logger.warning(f"Calculated volume is 0 for {symbol}. Skipping.")
                    continue
                    
                pipeline_stats.log_pass("risk_pass")
                    
                # DB Logging
                market_state = DatabaseLogger.log_market_state(
                    symbol=symbol,
                    timeframe=cfg.get("timeframe", "M5"),
                    close_price=features['close'],
                    indicators=features,
                    regime={"volatility_state": "HIGH_VOLATILITY" if features["is_high_volatility"] else "NORMAL"}
                )
                
                db_signal = DatabaseLogger.log_signal(
                    market_state_id=market_state.id,
                    strategy_name="V2_MultiScorer",
                    direction=direction,
                    market_score=market_score
                )
                
                acc_info = mt5.account_info()
                est_risk = (acc_info.balance * settings.RISK_PER_TRADE_PCT) if acc_info else 0.0
                daily_report.log_intended_execution(direction, volume, est_risk)
                
                logger.info(f"Executing {direction} on {symbol} with volume {volume}")
                decision_logger.log_step("Execution", True, f"DRY_RUN {direction} {volume} lots")
                
                Executor.execute_trade(
                    signal_id=db_signal.id,
                    symbol=symbol,
                    direction=direction,
                    volume=volume,
                    sl_points=sl_points,
                    probability=prob
                )
                pipeline_stats.log_pass("simulated_orders")
                
                decision_logger.print_tree(str(current_candle_time))
            
            # Print stats to fulfill user requirement "สรุปผลทุก 10 candles หรือทุก 30 นาที"
            # Since scan_markets already logs summary every 30 scans, we are good.
            
            interval = settings.MULTI_MARKET.get("scan_interval_seconds", 60)
            logger.info(f"Waiting {interval} seconds before next scan...")
            time.sleep(interval)
            
    except KeyboardInterrupt:
        logger.info("GoldBot stopped by user.")
    finally:
        mt5_client.disconnect()

if __name__ == "__main__":
    main()
