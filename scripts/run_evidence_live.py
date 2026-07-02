import os
import sys
import time
import json
import logging
from datetime import datetime

# Setup paths
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, base_dir)

import config.settings as settings
from data.mt5_client import mt5_client
from strategy.evidence_router import EvidenceRouter
from strategy.indicators import IndicatorCalculator
from execution.executor import Executor
from execution.shadow_executor import ShadowExecutor
from notifications.telegram_notifier import send_telegram

# Disable debug logs for urllib3
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("EvidenceLive")

def main():
    logger.info("==================================================")
    logger.info("🛡️ INITIALIZING EVIDENCE ROUTER LIVE SESSION 🛡️")
    is_dry_run = os.environ.get("DRY_RUN", "True").lower() == "true"
    logger.info(f"DRY_RUN: {is_dry_run}")
    logger.info("==================================================")
    
    if not mt5_client.connect():
        logger.error("Failed to connect to MT5")
        return

    send_telegram("🤖 <b>EvidenceRouter Live Session Started</b>\nMonitoring markets...")

    evidence_router = EvidenceRouter(base_dir, mode="LIVE")
    symbols = ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD", "NAS100", "US30", "USDJPY", "AUDUSD", "ETHUSD", "SPX500"]

    while True:
        try:
            logger.info("Scanning markets with EvidenceRouter...")
            for symbol in symbols:
                df = mt5_client.get_historical_data(symbol, "M15", 250)
                if df.empty:
                    continue
                
                df = IndicatorCalculator.add_indicators(df)
                
                import MetaTrader5 as mt5
                # Check Spread
                tick = mt5.symbol_info_tick(mt5_client.resolve_symbol(symbol))
                if tick:
                    spread_points = (tick.ask - tick.bid) / mt5.symbol_info(mt5_client.resolve_symbol(symbol)).point
                    if spread_points > 50:
                        logger.warning(f"[{symbol}] Spread too high: {spread_points} > 50. Skipping.")
                        continue
                
                signal = evidence_router.evaluate(df, symbol)
                if signal:
                    direction = signal['direction']
                    pf = signal['metadata']['historical_pf']
                    sim = signal['metadata']['similarity_score']
                    
                    logger.info(f"💡 [EVIDENCE LIVE] {symbol} {direction} | PF: {pf} | Sim: {sim}")
                    
                    # Notify Telegram
                    msg = (
                        f"🚀 <b>[EVIDENCE LIVE] EXECUTING TRADE!</b>\n"
                        f"─────────────────\n"
                        f"Symbol  : <b>{symbol}</b>\n"
                        f"Action  : <b>{direction}</b>\n"
                        f"Sim     : {sim * 100:.1f}%\n"
                        f"PF      : {pf:.2f}\n"
                        f"─────────────────\n"
                        f"<i>*Trade placed by EvidenceRouter</i>"
                    )
                    send_telegram(msg)
                    
                    # Execute
                    volume = 0.01  # Fixed for now or calculate from risk
                    sl_mult = signal['sl_mult']
                    tp_mult = signal['tp_mult']
                    
                    # Estimate SL points based on ATR
                    atr = df.iloc[-1]['atr']
                    sym_info = mt5.symbol_info(mt5_client.resolve_symbol(symbol))
                    point = sym_info.point if sym_info else 0.01
                    sl_points = int((atr * sl_mult) / point)
                    tp_points = int((atr * tp_mult) / point)
                    
                    if is_dry_run:
                        ShadowExecutor.execute_trade(
                            signal_id=0, symbol=symbol, direction=direction,
                            volume=volume, sl_points=sl_points
                        )
                    else:
                        Executor.execute_trade(
                            signal_id=0, symbol=symbol, direction=direction,
                            volume=volume, sl_points=sl_points, tp_points=tp_points
                        )
            
            logger.info("Scan complete. Waiting for next candle...")
            time.sleep(300)  # Wait 5 mins for next M15 candle roughly
            
        except Exception as e:
            logger.error(f"Error in Evidence Live loop: {e}", exc_info=True)
            time.sleep(60)

if __name__ == "__main__":
    main()
