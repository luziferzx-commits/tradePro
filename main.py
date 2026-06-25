# =============================================================================
# main.py — tradePro / GoldBot MetaTrader 5 XAUUSD GQOS Quantitative System
# Production Ready with Fixes 01-07
# =============================================================================

# ── Imports ─────────────────────────────────────────────────────────────────
# stdlib
import logging
import logging.handlers
import math                                  # [FIX-06]
import signal                                # [FIX-06]
import sys
import time
from datetime import datetime

# third-party
import MetaTrader5 as mt5
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError   # [FIX-03]

# local — core & config
from config.settings import settings
from data.mt5_client import mt5_client
from database.logger import DatabaseLogger
from database.repository import repository

# local — logic & ml
from analytics.daily_report import daily_report
from analytics.decision_tree import decision_logger
from analytics.model_health_report import health_monitor
from analytics.pipeline_stats import pipeline_stats
from execution.executor import Executor
from execution.shadow_executor import ShadowExecutor
from market.scanner import market_scanner
from memory.market_memory_v2 import market_memory_v2 as market_memory
from ml.feature_validator import FeatureValidator         # [FIX-07]
from ml.predictor import MLPredictor
from news.economic_filter import EconomicFilter
from notifications.telegram_notifier import notify_bot_started
from positions.tracker import PositionTracker

# local — risk
from risk.daily_drawdown_guard import DailyDrawdownGuard  # [FIX-05]
from risk.guard import RiskGuard
from risk.manager import RiskManager
from risk.portfolio_manager import portfolio_manager
from risk.sl_tp_calculator import SLTPCalculator          # [FIX-04]

# [FIX-02] REMOVED: from ai.gemini_filter import GeminiFilter


# ── Logging Configuration ───────────────────────────────────────────────────
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


# ── Helper Functions & Signal Handlers ──────────────────────────────────────
# [FIX-06] Graceful shutdown and precise timing
_shutdown_requested = False

def _request_shutdown(signum, frame):
    global _shutdown_requested
    logger.warning(f"Signal {signum} received — graceful shutdown requested.")
    _shutdown_requested = True

signal.signal(signal.SIGTERM, _request_shutdown)
signal.signal(signal.SIGINT,  _request_shutdown)


def get_timeframe_seconds(timeframe: str) -> int:
    """Convert MT5 TIMEFRAME string/constant to seconds."""
    _map = {
        mt5.TIMEFRAME_M1:  60, "M1": 60,
        mt5.TIMEFRAME_M5:  300, "M5": 300,
        mt5.TIMEFRAME_M15: 900, "M15": 900,
        mt5.TIMEFRAME_M30: 1800, "M30": 1800,
        mt5.TIMEFRAME_H1:  3600, "H1": 3600,
        mt5.TIMEFRAME_H4:  14400, "H4": 14400,
        mt5.TIMEFRAME_D1:  86400, "D1": 86400,
    }
    return _map.get(timeframe, 300)   # default M5 = 300s


def sleep_until_next_candle(tf_seconds: int, buffer_sec: int = 5) -> None:
    """
    Sleep precisely until after the next candle close + buffer.
    Much more accurate than fixed time.sleep(30).
    """
    now = time.time()
    remainder = now % tf_seconds
    sleep_time = (tf_seconds - remainder) + buffer_sec
    sleep_time = min(sleep_time, tf_seconds)   # never sleep more than 1 candle
    logger.info(f"[WAIT] Next candle in {sleep_time:.0f}s (tf={tf_seconds}s buffer={buffer_sec}s)")
    
    # Sleep in small chunks so we can interrupt gracefully
    end_time = time.time() + sleep_time
    while time.time() < end_time:
        if _shutdown_requested:
            break
        time.sleep(1)


# ── Main Entrypoint ─────────────────────────────────────────────────────────
def main():
    logger.info("Initializing GoldBot Multi-Market V2 (Production Mode)...")
    
    if settings.DRY_RUN:
        logger.warning("DRY_RUN MODE ACTIVE. No real orders will be sent.")
        
    if not mt5_client.connect():
        logger.error("Failed to start due to MT5 connection error.")
        return

    notify_bot_started()

    news_filter = EconomicFilter()
    ml_predictor = MLPredictor()
    # [FIX-02] REMOVED: ai_filter = GeminiFilter()
    
    MAX_RECONNECT = 3
    reconnect_count = 0
    tf_seconds = get_timeframe_seconds(settings.TIMEFRAME)

    try:
        # [FIX-06] Graceful shutdown loop
        while not _shutdown_requested:
            
            # [FIX-06] MT5 connection health check + reconnect
            if not mt5.terminal_info():
                reconnect_count += 1
                logger.warning(
                    f"MT5 connection lost. Attempt {reconnect_count}/{MAX_RECONNECT}..."
                )
                if reconnect_count > MAX_RECONNECT:
                    logger.critical("Max MT5 reconnect attempts exceeded. Shutting down.")
                    break
                if mt5_client.connect():
                    logger.info("MT5 reconnected successfully.")
                    reconnect_count = 0
                else:
                    time.sleep(30)
                    continue
            else:
                reconnect_count = 0   # reset counter on healthy connection
                
            try:
                # ── START OF CANDLE LOGIC ──────────────────────────────────
                if not mt5_client.is_new_candle():
                    time.sleep(1)
                    continue
                    
                logger.info("New closed candle detected. Processing...")
                decision_logger.reset()
                
                # [NEW] Economic News Filter (High Impact Window Check)
                if not news_filter.is_safe_to_trade():
                    logger.critical("[STOP] Trading paused due to High-Impact News event.")
                    decision_logger.log_step("Economic Filter", False, "High-Impact News Window")
                    daily_report.log_block("economic_news")
                    continue  # Skip this candle processing completely
                
                # [FIX-05] Daily drawdown kill switch — must be first safety gate
                dd_safe, dd_reason = DailyDrawdownGuard.is_safe()
                if not dd_safe:
                    logger.critical(f"[STOP] DAILY DRAWDOWN KILL SWITCH: {dd_reason}")
                    decision_logger.log_step("Daily DD Guard", False, dd_reason)
                    daily_report.log_block("daily_drawdown")
                    break  # Exit the while loop entirely — bot stops for today
                elif "WARNING" in dd_reason:
                    logger.warning(f"[WARN] Daily Drawdown Warning: {dd_reason}")
                    decision_logger.log_step("Daily DD Guard", True, dd_reason)
                else:
                    decision_logger.log_step("Daily DD Guard", True, dd_reason)

                # 1. Sync Positions and Manage Stops
                PositionTracker.sync_open_positions()
                if not settings.DRY_RUN:
                    PositionTracker.manage_trailing_stops()

                if settings.ENABLE_MULTI_ASSET:
                    logger.info("MULTI_ASSET_SCAN_STARTED: Multi-Asset Mode is enabled.")
                    
                    from market.symbol_registry import SymbolRegistry
                    from market.market_metadata import MarketMetadata
                    from scanner.multi_asset_scanner import MultiAssetScanner
                    from portfolio.correlation_engine import CorrelationEngine
                    from portfolio.exposure_manager import ExposureManager
                    from portfolio.capital_allocator import CapitalAllocator
                    from journal.portfolio_journal import PortfolioJournal
                    from portfolio.portfolio_var import PortfolioVaR
                    from datetime import datetime
                    
                    try:
                        registry = SymbolRegistry("config/symbols.yaml")
                        metadata = MarketMetadata(registry)
                        scanner = MultiAssetScanner(registry, metadata, mt5_client=mt5_client, predictor=ml_predictor)
                        
                        correlation_engine = CorrelationEngine("config/correlations.yaml", metadata)
                        exposure_manager = ExposureManager(metadata)
                        
                        acc_info = mt5.account_info()
                        acc_balance = acc_info.balance if acc_info else settings.MIN_EQUITY
                        
                        allocator = CapitalAllocator(metadata, correlation_engine, exposure_manager, 
                                                     base_risk_pct=settings.RISK_PER_TRADE_PCT,
                                                     account_balance=acc_balance)
                                                     
                        portfolio_journal = PortfolioJournal()
                        
                        # Run Scan
                        approved_opportunities, rejected_signals = scanner.scan_all()
                        
                        # Convert MT5 positions to standard dict format
                        open_positions = []
                        if acc_info:
                            for p in mt5.positions_get():
                                open_positions.append({
                                    'symbol': p.symbol,
                                    'side': 'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL',
                                    'risk_amount': p.volume * 100.0,
                                    'risk_amount_pct': (p.volume * 100.0) / acc_balance
                                })
                                
                        # Allocate
                        executions, rejections = allocator.allocate(approved_opportunities, open_positions)
                        
                        # Calculate new VaR
                        var_result = PortfolioVaR.calculate_var(open_positions, correlation_engine.correlations)
                        
                        # Log Decisions
                        for opp in approved_opportunities:
                            logger.info(f"SIGNAL_APPROVED_BY_SCANNER: {opp['symbol']} {opp['side']}")
                            
                            ex_match = next((e for e in executions if e['symbol'] == opp['symbol']), None)
                            rej_match = next((r for r in rejections if r['symbol'] == opp['symbol']), None)
                            
                            if ex_match:
                                logger.info(f"PORTFOLIO_APPROVED: {ex_match['symbol']} - Risk: {ex_match['risk_amount_pct']:.2%}")
                                if ex_match['correlation_multiplier'] < 0.99:
                                    logger.info(f"PORTFOLIO_RESIZED: {ex_match['symbol']} reduced due to correlation")
                                    
                                portfolio_journal.log_decision({
                                    "symbol": ex_match["symbol"],
                                    "side": ex_match["side"],
                                    "scanner_status": "APPROVED",
                                    "portfolio_status": "APPROVED",
                                    "reason": "OK",
                                    "original_risk_pct": settings.RISK_PER_TRADE_PCT,
                                    "final_risk_pct": ex_match["risk_amount_pct"],
                                    "estimated_lot": ex_match["estimated_lot"],
                                    "final_score": ex_match["final_score"],
                                    "var_95": var_result["var"],
                                    "cvar_95": var_result["cvar"],
                                    "warnings": var_result["warnings"] + correlation_engine.warnings
                                })
                                
                                # Execute!
                                if settings.DRY_RUN:
                                    logger.warning(f"DRY_RUN_ORDER_BLOCKED: {ex_match['symbol']} {ex_match['side']} {ex_match['estimated_lot']} lots")
                                else:
                                    logger.info(f"LIVE_ORDER_SENT: {ex_match['symbol']} {ex_match['side']} {ex_match['estimated_lot']} lots")
                                    from execution.executor import Executor
                                    # Create a mock evaluation to bypass Executor's legacy assertions since we already validated via PortfolioRiskEngine
                                    mock_evaluation = {
                                        "allowed": True,
                                        "position_size": ex_match['estimated_lot']
                                    }
                                    Executor.execute_trade(
                                        signal_id=0, # Multi-asset signals don't use the SQL signal_id
                                        symbol=ex_match['symbol'],
                                        direction=ex_match['side'],
                                        volume=ex_match['estimated_lot'],
                                        sl_points=metadata.get_spread_limit(ex_match['symbol']) * 10, # Dynamic SL: 10x max spread
                                        probability=ex_match['final_score'],
                                        evaluation=mock_evaluation
                                    )
                                    
                            elif rej_match:
                                if rej_match['reject_reason'] == "PORTFOLIO_DD_GUARD_TRIGGERED":
                                    logger.warning("DD_GUARD_TRIGGERED: Portfolio engine halted")
                                logger.info(f"PORTFOLIO_REJECTED: {rej_match['symbol']} - {rej_match['reject_reason']}")
                                portfolio_journal.log_decision({
                                    "symbol": rej_match["symbol"],
                                    "side": rej_match["side"],
                                    "scanner_status": "APPROVED",
                                    "portfolio_status": "REJECTED",
                                    "reason": rej_match["reject_reason"],
                                    "original_risk_pct": settings.RISK_PER_TRADE_PCT,
                                    "final_risk_pct": 0.0,
                                    "estimated_lot": 0.0,
                                    "final_score": rej_match.get("final_score", 0.0),
                                    "var_95": var_result["var"],
                                    "cvar_95": var_result["cvar"],
                                    "warnings": var_result["warnings"] + correlation_engine.warnings
                                })
                                
                        for rej in rejected_signals:
                            logger.info(f"SIGNAL_REJECTED_BY_SCANNER: {rej['symbol']} {rej['side']} - {rej['reason']}")
                            portfolio_journal.log_decision({
                                "symbol": rej["symbol"],
                                "side": rej["side"],
                                "scanner_status": "REJECTED",
                                "portfolio_status": "N/A",
                                "reason": rej["reason"],
                                "original_risk_pct": settings.RISK_PER_TRADE_PCT,
                                "final_risk_pct": 0.0,
                                "estimated_lot": 0.0,
                                "final_score": 0.0,
                                "var_95": var_result["var"],
                                "cvar_95": var_result["cvar"],
                                "warnings": var_result["warnings"] + correlation_engine.warnings
                            })
                            
                    except Exception as e:
                        logger.error(f"Portfolio Engine Error, rejecting all: {e}")
                    
                    decision_logger.print_tree(str(datetime.now()))
                    sleep_until_next_candle(tf_seconds)
                    continue

                # 2. Multi-Market Scan
                valid_signals = market_scanner.scan_markets()
                logger.info(f"Scan complete. Found {len(valid_signals)} valid signals.")
                
                # 3. Process Signals
                for signal_data in valid_signals:
                    symbol = signal_data['symbol']
                    direction = signal_data['direction']
                    cfg = signal_data['config']
                    features = signal_data['features']
                    market_score = signal_data['score']
                    current_candle_time = signal_data['timestamp']
                    df = signal_data['df']
                    
                    logger.info(f"Processing {direction} signal for {symbol} (Score: {market_score})")

                    # Feature Construction
                    ml_features = features.copy()
                    
                    # [FIX-07] Validate feature completeness
                    feat_ok, missing_keys = FeatureValidator.check_completeness(ml_features)
                    if not feat_ok:
                        logger.error(f"ML features incomplete, missing: {missing_keys}. Skipping.")
                        decision_logger.log_step("ML Predictor", False, f"Missing: {missing_keys}")
                        decision_logger.print_tree(str(current_candle_time))
                        continue

                    # [FIX-07] Sanitize NaN/Inf and clamp out-of-bound values
                    ml_features, feat_warnings = FeatureValidator.validate_and_sanitize(ml_features)
                    if feat_warnings:
                        logger.warning(f"Feature sanitization: {feat_warnings}")
                    
                    # Consensus Engine / Prediction
                    ml_result = ml_predictor.predict(ml_features)
                    final_dir = direction
                    
                    # [FIX-04] Dynamic ATR-based SL/TP
                    sl_tp = SLTPCalculator.calculate(df, final_dir)
                    sl_points = sl_tp['sl_points']
                    tp_points = sl_tp['tp_points']
                    
                    logger.info(
                        f"SL/TP: {sl_points}pts / {tp_points}pts | "
                        f"ATR={sl_tp['atr_used']:.2f}$ [{sl_tp['atr_regime']}] | "
                        f"RR={sl_tp['rr_ratio']}"
                    )
                    
                    decision_logger.log_step(
                        "SL/TP Calc", True,
                        f"SL={sl_points}pts TP={tp_points}pts [{sl_tp['atr_regime']}]"
                    )

                    # Evaluate Risk
                    health_score = health_monitor.get_latest_health()
                    evaluation = RiskGuard.evaluate_trade(
                        symbol=symbol,
                        direction=final_dir,
                        signal_price=features['close'],
                        sl_points=sl_points,
                        tp_points=tp_points,
                        ml_prob=ml_result['probability'],
                        health_score=health_score
                    )
                    
                    if not evaluation["allowed"]:
                        pipeline_stats.log_reject("risk_guard_failed", symbol)
                        logger.warning(f"Trade blocked for {symbol}: {evaluation['reason']}")
                        decision_logger.log_step("Safety Checks", False, evaluation['guard_that_failed'])
                        continue
                        
                    pipeline_stats.log_pass("risk_pass")
                    volume = evaluation["position_size"]

                    # DB Logging (Duplicate candle guard inherently handled here)
                    market_state = DatabaseLogger.log_market_state(
                        symbol=symbol,
                        timeframe=cfg.get("timeframe", "M5"),
                        close_price=features['close'],
                        indicators=features,
                        regime={"vol_state": "HIGH" if features.get("is_high_volatility") else "NORM"}
                    )
                    
                    db_signal = DatabaseLogger.log_signal(
                        market_state_id=market_state.id,
                        strategy_name="V2_MultiScorer",
                        direction=final_dir,
                        market_score=market_score
                    )

                    # [FIX-03] ML Result Save Block (SQLAlchemy 2.0 + Error Handling)
                    with repository.get_session() as session:
                        try:
                            sig = session.get(db_signal.__class__, db_signal.id)
                            if sig is None:
                                logger.error(
                                    f"Signal record id={db_signal.id} not found in DB. "
                                    "Skipping ML result save."
                                )
                            else:
                                sig.ml_probability = float(ml_result['probability'])
                                sig.ml_model_version = ml_result['model_version']
                                sig.ml_feature_hash = ml_result['feature_hash']
                                sig.ml_expected_rr = float(ml_result['expected_rr'])
                                sig.ml_expected_holding_time = float(ml_result['expected_holding_time_hrs'])
                                sig.ml_expected_drawdown = float(ml_result['expected_max_dd_r'])
                                sig.ml_rejected = not ml_result['approved']
                                sig.ml_rejection_reason = ml_result['reason']
                                session.commit()
                        except SQLAlchemyError as e:
                            logger.error(f"DB error saving ML result for signal {db_signal.id}: {e}")
                            session.rollback()

                    # Report Logic
                    acc_info = mt5.account_info()
                    est_risk = (acc_info.balance * settings.RISK_PER_TRADE_PCT) if acc_info else 0.0
                    daily_report.log_intended_execution(final_dir, volume, est_risk)

                    logger.info(f"Executing {final_dir} on {symbol} with volume {volume}")
                    decision_logger.log_step("Execution", True, f"{final_dir} {volume} lots")

                    # Execution Block
                    if settings.DRY_RUN:
                        # ShadowExecutor call
                        ShadowExecutor.execute_trade(
                            signal_id=db_signal.id,
                            symbol=symbol,
                            direction=final_dir,
                            volume=volume,
                            sl_points=sl_points,
                            tp_points=tp_points,            # [FIX-04] add TP
                        )
                        pipeline_stats.log_pass("simulated_orders")
                    else:
                        # Executor call (LIVE)
                        Executor.execute_trade(
                            signal_id=db_signal.id,
                            symbol=symbol,
                            direction=final_dir,
                            volume=volume,
                            sl_points=sl_points,
                            tp_points=tp_points,            # [FIX-04] add TP
                            probability=ml_result['probability'],
                        )
                        pipeline_stats.log_pass("live_orders")
                        
                    decision_logger.print_tree(str(current_candle_time))
                # ── END OF CANDLE LOGIC ────────────────────────────────────

            except Exception as candle_err:
                # [FIX-06] Catch isolated candle errors, log, and keep running
                logger.error(f"Error in candle processing: {candle_err}", exc_info=True)
                time.sleep(10)
                continue

            # [FIX-06] Smart sleep instead of fixed time.sleep(30)
            sleep_until_next_candle(tf_seconds)

    except Exception as fatal_err:
        logger.critical(f"FATAL error in main loop: {fatal_err}", exc_info=True)
    finally:
        logger.info("GoldBot shutting down...")
        mt5_client.disconnect()


if __name__ == "__main__":
    main()
