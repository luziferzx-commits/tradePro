import logging
import threading
import time
from typing import Optional
from decimal import Decimal
import MetaTrader5 as mt5

from gqos.messaging.bus import ICommandBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.common.enums import TradeDirection
from gqos.sizing.events import SizePositionCommand

from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from scanner.multi_asset_scanner import MultiAssetScanner
from ml.predictor import MLPredictor
from data.mt5_client import MT5Client
from strategy.strategies.registry import StrategyRegistry
from strategy.strategies.ensemble_router import EnsembleRouter
from strategy.evidence_router import EvidenceRouter

# ─── Learning Loop ─────────────────────────────────────────────────
from gqos.learning.outcome_logger import outcome_logger
# ───────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

class AlphaWorker:
    """
    Background worker that runs the Alpha Generation (Scanner + Predictor) loop
    and pushes Trade Intent commands to the GQOS Event Bus.
    """
    def __init__(self, cmd_bus: ICommandBus):
        self._cmd_bus = cmd_bus
        self._running = False
        self._thread = None
        self.is_paused = False
        
        self.registry = SymbolRegistry("config/symbols.yaml")
        self.metadata = MarketMetadata(self.registry)
        self.mt5_client = MT5Client()
        self.predictor = MLPredictor()
        
        import os
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.evidence_router = EvidenceRouter(base_dir=base_dir, mode="LIVE")
        
        self.abc_router = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.0)
        
        self.scanner = MultiAssetScanner(self.registry, self.metadata, self.mt5_client, self.predictor)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("AlphaWorker started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("AlphaWorker stopped.")

    def _run_loop(self):
        while self._running:
            try:
                if self.is_paused:
                    time.sleep(1)
                    continue
                    
                if not self.mt5_client.is_new_candle():
                    time.sleep(1)
                    continue

                logger.info("AlphaWorker: New closed candle detected. Scanning markets...")
                
                # 1. Run Legacy MultiAssetScanner
                approved, rejected = self.scanner.scan_all()
                
                # 2. Run EvidenceRouter
                evidence_signals = []
                try:
                    from strategy.indicators import IndicatorCalculator
                    symbols_to_scan = [m["symbol"] for m in self.registry.get_enabled_symbols()]
                    for symbol in symbols_to_scan:
                        df = self.mt5_client.get_historical_data(symbol, "M15", 250)
                        if df is None or df.empty: continue
                        df = IndicatorCalculator.add_indicators(df)
                        
                        sig = self.evidence_router.evaluate(df, symbol)
                        if sig:
                            evidence_signals.append({
                                'symbol':            symbol,
                                'side':              sig['direction'],
                                'model_probability': float(sig.get('confidence', 0.95)),
                                'atr':               float(df.iloc[-1]['atr']),
                                'source':            'EVIDENCE_ROUTER',
                                # ─── ส่ง metadata ไปด้วย เพื่อ Learning Loop ───
                                'metadata':          sig.get('metadata', {}),
                                # ─────────────────────────────────────────────────
                            })
                            logger.info(
                                f"💡 EvidenceRouter Signal: {symbol} {sig['direction']} "
                                f"(Sim: {sig['metadata']['similarity_score']:.2f})"
                            )
                except Exception as e:
                    logger.error(f"AlphaWorker EvidenceRouter scan failed: {e}", exc_info=True)
                
                # 3. Run ABC EnsembleRouter
                abc_signals = []
                try:
                    from market.regime_detector import RegimeDetector
                    for symbol in symbols_to_scan:
                        df = self.mt5_client.get_historical_data(symbol, "M15", 250)
                        if df is None or df.empty: continue
                        df = IndicatorCalculator.add_indicators(df)
                        regime = RegimeDetector.detect(df)
                        registry = StrategyRegistry(symbol, "M15")
                        decision = self.abc_router.route(df, regime, registry, ml_predictions=None, session_info=None)
                        if decision.direction != "NEUTRAL":
                            abc_signals.append({
                                'symbol':            symbol,
                                'side':              decision.direction,
                                'model_probability': float(decision.edge_score) if decision.edge_score > 0 else 0.8,
                                'atr':               float(df.iloc[-1]['atr']),
                                'source':            'ABC_ROUTER',
                                'strategy_id':       'gqos_alpha_v1',
                                'metadata':          {},   # ABC ยังไม่มี pattern_id
                            })
                            logger.info(f"💡 ABC Signal: {symbol} {decision.direction} (EV: {decision.edge_score:.2f})")
                except Exception as e:
                    logger.error(f"AlphaWorker ABC scan failed: {e}", exc_info=True)

                # Combine all signals
                approved.extend(evidence_signals)
                approved.extend(abc_signals)

                # --- 4. Apply Social Sentiment (Fear & Greed) for Crypto ---
                try:
                    from strategy.crypto_sentiment import CryptoSentiment
                    crypto_symbols = ["BTCUSD", "ETHUSD", "XRPUSD", "SOLUSD", "BTCUSDm", "ETHUSDm", "XRPUSDm", "SOLUSDm"]
                    has_crypto_signals = any(sig['symbol'] in crypto_symbols for sig in approved + rejected)
                    if has_crypto_signals:
                        fng = CryptoSentiment.get_fear_greed_index()
                        fng_val = fng['value']
                        
                        # Contrarian Force Approve: Extreme Fear (< 20) -> Force BUY
                        if fng_val < 20:
                            for sig in rejected:
                                if sig['symbol'] in crypto_symbols and sig['side'] in ["BUY", "LONG"]:
                                    sig['model_probability'] = 0.85
                                    sig['status'] = 'APPROVED'
                                    sig['reason'] = 'Force Approved (Extreme Fear Contrarian)'
                                    if 'metadata' not in sig:
                                        sig['metadata'] = {}
                                    approved.append(sig)
                                    logger.info(f"🚀 [Contrarian Force] {sig['symbol']} BUY rescued from Rejection due to Extreme Fear ({fng_val})!")
                                    
                        for sig in approved:
                            if sig['symbol'] in crypto_symbols:
                                side = sig['side']
                                # Fear < 25 + BUY -> boost confidence
                                if fng_val < 25 and side in ["BUY", "LONG"]:
                                    old_conf = sig['model_probability']
                                    sig['model_probability'] = min(0.99, old_conf * 1.2)
                                    logger.info(f"🚀 [Sentiment Boost] {sig['symbol']} BUY + Extreme Fear ({fng_val}): Conf {old_conf:.2f} -> {sig['model_probability']:.2f}")
                                # Greed > 75 + SELL -> boost confidence
                                elif fng_val > 75 and side in ["SELL", "SHORT"]:
                                    old_conf = sig['model_probability']
                                    sig['model_probability'] = min(0.99, old_conf * 1.2)
                                    logger.info(f"🚀 [Sentiment Boost] {sig['symbol']} SELL + Extreme Greed ({fng_val}): Conf {old_conf:.2f} -> {sig['model_probability']:.2f}")
                except Exception as e:
                    logger.warning(f"Failed to apply Crypto Sentiment: {e}")
                # ------------------------------------------------------------
                
                logger.info(
                    f"AlphaWorker: Scan complete. {len(approved)} signals approved "
                    f"({len(evidence_signals)} from Evidence). Processing signals..."
                )

                for sig in approved:
                    symbol = sig['symbol']
                    side   = sig['side']
                    direction = TradeDirection.BUY if side in ["BUY", "LONG"] else TradeDirection.SELL
                    
                    resolved_symbol = self.mt5_client.resolve_symbol(symbol)
                    sym_info = mt5.symbol_info(resolved_symbol)
                    if not sym_info:
                        logger.error(f"Could not get symbol info for {resolved_symbol}")
                        continue
                        
                    positions = mt5.positions_get(symbol=resolved_symbol)
                    if positions and len(positions) > 0:
                        logger.info(f"AlphaWorker: Skipping {resolved_symbol} as there is already an open position.")
                        continue
                        
                    entry_price = Decimal(str(sym_info.ask if direction == TradeDirection.BUY else sym_info.bid))
                    conviction  = Decimal(str(sig.get('model_probability', 0.5)))
                    
                    point = Decimal(str(sym_info.point))
                    atr   = Decimal(str(sig.get('atr', 0.0)))
                    
                    symbol_config  = self.registry.get_symbol(symbol) or {}
                    atr_multiplier = Decimal(str(symbol_config.get("atr_sl_multiplier", 15.0)))
                    
                    sl_buffer = atr * atr_multiplier if atr > 0 else Decimal('500') * point
                    sl_price  = (entry_price - sl_buffer) if direction == TradeDirection.BUY \
                                else (entry_price + sl_buffer)
                    tp_buffer = sl_buffer * Decimal('2.0')
                    tp_price  = (entry_price + tp_buffer) if direction == TradeDirection.BUY \
                                else (entry_price - tp_buffer)

                    # ─── Learning Loop: บันทึกก่อนส่ง command ───────────────
                    meta = sig.get('metadata') or {}
                    try:
                        outcome_logger.on_trade_opened(
                            symbol=resolved_symbol,
                            direction=direction.name,
                            entry_price=float(entry_price),
                            sl_price=float(sl_price),
                            tp_price=float(tp_price),
                            pattern_id=meta.get('pattern_id'),
                            pattern_pf=float(meta.get('historical_pf', 0.0)),
                            pattern_sim=float(meta.get('similarity_score', 0.0)),
                            session=meta.get('session_label', 'Unknown'),
                            strategy_id="gqos_alpha_v1",
                        )
                    except Exception as e:
                        logger.warning(f"[Learning] on_trade_opened failed: {e}")
                    # ────────────────────────────────────────────────────────

                    if hasattr(self, 'position_monitor'):
                        try:
                            self.position_monitor.register_open(
                                symbol=resolved_symbol,
                                edge_score=float(conviction)
                            )
                        except Exception as e:
                            logger.warning(f"[PositionMonitor] register_open failed: {e}")

                    cmd = SizePositionCommand(
                        strategy_id="gqos_alpha_v1",
                        symbol=resolved_symbol,
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss_price=sl_price,
                        take_profit_price=tp_price,
                        conviction=conviction,
                        metrics=None,
                        volatility=None
                    )
                    
                    logger.info(
                        f"AlphaWorker: Emitting SizePositionCommand for {resolved_symbol} "
                        f"{direction.name} SL={sl_price:.5f}"
                    )
                    self._cmd_bus.dispatch(MessageEnvelope.create(payload=cmd, version=1))
                
                logger.info("AlphaWorker: Sleeping 60s...")
                for _ in range(60):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in AlphaWorker loop: {e}")
                time.sleep(5)
