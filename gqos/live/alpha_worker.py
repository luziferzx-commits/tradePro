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
from config.settings import settings

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
        self.guard_probe_reason = ""
        # Optional callback (set by the live runner) to auto-clear daily guard
        # pauses when the block window rolls over; returns a message or None.
        self._guard_reevaluate = None
        
        self.registry = SymbolRegistry("config/symbols.yaml")
        self.metadata = MarketMetadata(self.registry)
        self.mt5_client = MT5Client()
        self.predictor = MLPredictor()
        
        import os
        from datetime import datetime
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.run_id = os.getenv("GQOS_RUN_ID") or f"live-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        self.learning_source = settings.LEARNING_SOURCE
        self.evidence_router = EvidenceRouter(base_dir=base_dir, mode="LIVE", mt5_client=self.mt5_client)
        
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
                # Auto-clear daily guard pauses (e.g. at day rollover) so the
                # bot resumes trading without a manual restart.
                if self._guard_reevaluate is not None:
                    try:
                        _msg = self._guard_reevaluate()
                        if _msg:
                            logger.warning("[LiveGuard] %s", _msg)
                    except Exception as _e:
                        logger.debug(f"guard reevaluate failed: {_e}")

                # Intraday cutoff: stop opening new trades at/after the EOD flat
                # close hour so nothing is opened just to be liquidated overnight.
                _eod = getattr(settings, "DAILY_FLAT_CLOSE_HOUR_UTC", -1)
                if _eod is not None and int(_eod) >= 0:
                    from datetime import datetime, timezone
                    if datetime.now(timezone.utc).hour >= int(_eod):
                        time.sleep(5)
                        continue

                paused_scan_only = self.is_paused and settings.ENABLE_PAUSED_SIGNAL_LOGGING
                if self.is_paused and not paused_scan_only:
                    time.sleep(1)
                    continue

                if not self.mt5_client.is_new_candle():
                    time.sleep(1)
                    continue

                logger.info("AlphaWorker: New closed candle detected. Scanning markets...")
                if paused_scan_only:
                    logger.info("AlphaWorker: Entry paused; scanning for signal logging only.")
                
                # 1. Run Legacy MultiAssetScanner
                approved, rejected = self.scanner.scan_all()
                
                # 2. Run EvidenceRouter
                evidence_signals = []
                try:
                    from strategy.indicators import IndicatorCalculator
                    import uuid
                    from datetime import datetime
                    symbols_to_scan = [m["symbol"] for m in self.registry.get_enabled_symbols()]
                    for symbol in symbols_to_scan:
                        now_str = datetime.utcnow().strftime("%Y%m%d")
                        decision_id = f"GQOS-{now_str}-{str(uuid.uuid4().hex[:8].upper())}"
                        df = self.mt5_client.get_historical_data(symbol, "M15", 250)
                        if df is None or len(df) < 2: continue
                        
                        # ตัดแท่งที่กำลังวิ่งออก ป้องกัน repaint
                        df = df.iloc[:-1]
                        
                        df = IndicatorCalculator.add_indicators(df)
                        
                        sig = self.evidence_router.evaluate(df, symbol, decision_id)
                        if sig:
                            evidence_signals.append({
                                'symbol':            symbol,
                                'side':              sig['direction'],
                                'model_probability': float(sig.get('confidence', 0.95)),
                                'atr':               float(df.iloc[-1]['atr']),
                                'source':            'EVIDENCE_ROUTER',
                                # ─── ส่ง metadata ไปด้วย เพื่อ Learning Loop ───
                                'metadata':          sig.get('metadata', {}),
                                'decision_id':       decision_id,
                                # ─────────────────────────────────────────────────
                            })
                            logger.info(
                                f"💡 EvidenceRouter Signal: {symbol} {sig['direction']} "
                                f"(Sim: {(sig.get('metadata') or {}).get('similarity', 0):.2f})"
                            )
                except Exception as e:
                    logger.error(f"AlphaWorker EvidenceRouter scan failed: {e}", exc_info=True)
                
                # 3. Run ABC EnsembleRouter
                abc_signals = []
                try:
                    from market.regime_detector import RegimeDetector
                    from strategy.indicators import IndicatorCalculator
                    for symbol in symbols_to_scan:
                        df = self.mt5_client.get_historical_data(symbol, "M15", 250)
                        if df is None or len(df) < 2: continue
                        
                        # ตัดแท่งที่กำลังวิ่งออก ป้องกัน repaint
                        df = df.iloc[:-1]
                        
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
                        
                        # Optional contrarian rescue. Keep disabled by default in live mode
                        # because it can reintroduce crypto signals rejected by other filters.
                        if settings.ENABLE_CRYPTO_FORCE_APPROVE and fng_val < 20:
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

                try:
                    from gqos.ops.demo_exploration import build_demo_exploration_candidates
                    exploration_signals = build_demo_exploration_candidates(self.registry, self.mt5_client, approved)
                    if exploration_signals:
                        approved.extend(exploration_signals)
                        logger.warning(
                            "AlphaWorker: Added %s DEMO_EXPLORATION probe signals for live learning.",
                            len(exploration_signals),
                        )
                except Exception as e:
                    logger.warning(f"[DemoExplore] Candidate build failed: {e}")
                
                logger.info(
                    f"AlphaWorker: Scan complete. {len(approved)} signals approved "
                    f"({len(evidence_signals)} from Evidence). Processing signals..."
                )

                guard_probe_active = bool(getattr(self, "guard_probe_reason", ""))
                
                # Deduplicate signals by symbol to prevent duplicate limit orders
                unique_approved = {}
                for sig in approved:
                    sym = sig['symbol']
                    conf = float(sig.get('model_probability', 0.5))
                    if sym not in unique_approved or conf > float(unique_approved[sym].get('model_probability', 0.5)):
                        unique_approved[sym] = sig
                approved = list(unique_approved.values())

                for sig in approved:
                    if paused_scan_only:
                        logger.info(
                            "AlphaWorker: Entry paused; signal logged but no live order will be sent "
                            f"for {sig.get('symbol')} {sig.get('side')}."
                        )
                        continue

                    symbol = sig['symbol']
                    side   = sig['side']
                    direction = TradeDirection.BUY if side in ["BUY", "LONG"] else TradeDirection.SELL
                    decision_id = sig.get('decision_id')
                    if not decision_id:
                        import uuid
                        import datetime
                        date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
                        decision_id = f"GQOS-{date_str}-{str(uuid.uuid4().hex[:8].upper())}"
                        sig['decision_id'] = decision_id
                    
                    resolved_symbol = self.mt5_client.resolve_symbol(symbol)
                    sym_info = mt5.symbol_info(resolved_symbol)
                    if not sym_info:
                        logger.error(f"Could not get symbol info for {resolved_symbol}")
                        continue

                    symbol_config = self.registry.get_symbol(symbol) or {}
                    max_spread = symbol_config.get("max_spread_points")
                    if max_spread is not None and sym_info.spread > float(max_spread):
                        logger.warning(
                            f"AlphaWorker: Skipping {resolved_symbol}; "
                            f"spread too high ({sym_info.spread} > {max_spread})."
                        )
                        continue
                        
                    positions = mt5.positions_get(symbol=resolved_symbol)
                    if positions and len(positions) > 0:
                        logger.info(f"AlphaWorker: Skipping {resolved_symbol} as there is already an open position.")
                        continue
                        
                    entry_price = Decimal(str(sym_info.ask if direction == TradeDirection.BUY else sym_info.bid))
                    conviction  = Decimal(str(sig.get('model_probability', 0.5)))
                    
                    point = Decimal(str(sym_info.point))
                    atr   = Decimal(str(sig.get('atr', 0.0)))
                    
                    atr_multiplier = Decimal(str(symbol_config.get("atr_sl_multiplier", 15.0)))
                    
                    base_sl_buffer = atr * atr_multiplier if atr > 0 else Decimal('500') * point
                    
                    # Apply Dynamic Target ML with Clamping
                    try:
                        from ml.dynamic_targets import dynamic_targets
                        meta = sig.get('metadata') or {}
                        pattern_sim = float(meta.get('similarity', meta.get('similarity_score', 0.5)))
                        pred_sl, pred_tp = dynamic_targets.predict(pattern_sim, float(base_sl_buffer))
                        
                        # Clamp to safety bounds (0.5x to 2.0x of static ATR buffer)
                        min_sl = float(base_sl_buffer) * 0.5
                        max_sl = float(base_sl_buffer) * 2.0
                        
                        clamped_sl = max(min_sl, min(max_sl, pred_sl))
                        clamped_tp = max(min_sl * 2.0, min(max_sl * 2.0, pred_tp))
                        
                        sl_buffer = Decimal(str(clamped_sl))
                        tp_buffer = Decimal(str(clamped_tp))
                    except Exception as e:
                        logger.error(f"Dynamic targets failed: {e}")
                        sl_buffer = base_sl_buffer
                        tp_buffer = sl_buffer * Decimal('2.0')
                        
                    sl_price  = (entry_price - sl_buffer) if direction == TradeDirection.BUY \
                                else (entry_price + sl_buffer)
                    tp_price  = (entry_price + tp_buffer) if direction == TradeDirection.BUY \
                                else (entry_price - tp_buffer)

                    # ─── Learning Loop: บันทึกก่อนส่ง command ───────────────
                    meta = sig.get('metadata') or {}
                    account = mt5.account_info()
                    account_id = str(getattr(account, "login", "") or "")
                    entry_mode = str(meta.get("entry_mode_override") or ("GUARDED_PROBE" if guard_probe_active else "NORMAL"))
                    probe_reason = str(meta.get("probe_reason") or (self.guard_probe_reason if guard_probe_active else ""))
                    sim_rec = meta.get("simulation_recommendation") or {}
                    try:
                        outcome_logger.register_intent(
                            decision_id=decision_id,
                            symbol=resolved_symbol,
                            direction=direction.name,
                            entry_price=float(entry_price),
                            sl_price=float(sl_price),
                            tp_price=float(tp_price),
                            pattern_id=meta.get('pattern_id'),
                            pattern_pf=float(meta.get('profit_factor', meta.get('historical_pf', 0.0))),
                            pattern_sim=float(meta.get('similarity', meta.get('similarity_score', 0.0))),
                            session=meta.get('session_label', 'Unknown'),
                            strategy_id="gqos_alpha_v1",
                            source=self.learning_source,
                            run_id=self.run_id,
                            account_id=account_id,
                            entry_mode=entry_mode,
                            probe_reason=probe_reason,
                            extra_metadata={
                                "promotion_status": meta.get("promotion_status"),
                                "regime": meta.get("regime"),
                                "atr_bucket": meta.get("atr_bucket"),
                                "expectancy_r": meta.get("expectancy_r"),
                                "occurrences": meta.get("occurrences"),
                                "simulation_action": sim_rec.get("action"),
                                "simulation_soft_rule": sim_rec.get("soft_rule"),
                                "simulation_confidence": sim_rec.get("confidence"),
                                "simulation_avg_r": sim_rec.get("avg_r"),
                                "simulation_win_rate": sim_rec.get("win_rate"),
                                "simulation_samples": sim_rec.get("samples"),
                                "pa_h4_trend": meta.get("pa_h4_trend"),
                                "pa_h4_divergence": meta.get("pa_h4_divergence"),
                                "pa_liquidity_sweep": meta.get("pa_liquidity_sweep"),
                                "pa_fvg_aligned": meta.get("pa_fvg_aligned"),
                                "pa_h1_chop": meta.get("pa_h1_chop"),
                                "pa_killzone": meta.get("pa_killzone"),
                                "pa_usd_basket_trend": meta.get("pa_usd_basket_trend"),
                            },
                        )
                    except Exception as e:
                        logger.warning(f"[Learning] on_trade_opened failed: {e}")
                    # ────────────────────────────────────────────────────────

                    if hasattr(self, 'position_monitor'):
                        try:
                            self.position_monitor.register_intent(
                                decision_id=decision_id,
                                symbol=resolved_symbol,
                                edge_score=float(conviction)
                            )
                        except Exception as e:
                            logger.warning(f"[PositionMonitor] register_open failed: {e}")

                    if settings.ENABLE_PAUSED_SYMBOL_RECOVERY_PROBE:
                        try:
                            from gqos.risk.portfolio_budget import portfolio_budget
                            from strategy.cooldown_manager import cooldown_manager

                            budget_multiplier = portfolio_budget.get_multiplier(resolved_symbol)
                            historical_pf = float(meta.get('profit_factor', meta.get('historical_pf', 0.0)))
                            expectancy_r = float(meta.get('expectancy_r', 0.0))
                            similarity = float(meta.get('similarity', meta.get('similarity_score', 0.0)))
                            if (
                                budget_multiplier <= 0.0
                                and historical_pf >= settings.RECOVERY_PROBE_MIN_PF
                                and expectancy_r >= settings.RECOVERY_PROBE_MIN_EXPECTANCY_R
                                and similarity >= settings.RECOVERY_PROBE_MIN_SIMILARITY
                            ):
                                cooldown_manager.set_probe(decision_id, True)
                                outcome_logger.update_intent(
                                    decision_id,
                                    entry_mode="RECOVERY_PROBE",
                                    probe_reason="symbol budget paused; strong recovery signal",
                                )
                                logger.warning(
                                    f"[RecoveryProbe] {resolved_symbol} budget paused but signal is strong; "
                                    f"allowing {settings.LIVE_GUARD_PROBE_MULTIPLIER:.2f}x probe "
                                    f"(PF={historical_pf:.2f}, ExpR={expectancy_r:.2f}, Sim={similarity:.2f})"
                                )
                        except Exception as e:
                            logger.warning(f"[RecoveryProbe] Could not evaluate probe override for {resolved_symbol}: {e}")

                    if guard_probe_active:
                        try:
                            from strategy.cooldown_manager import cooldown_manager
                            cooldown_manager.set_probe(decision_id, True)
                            outcome_logger.update_intent(
                                decision_id,
                                entry_mode="GUARDED_PROBE",
                                probe_reason=self.guard_probe_reason,
                            )
                            logger.warning(
                                f"[GuardedProbe] {resolved_symbol} {direction.name} allowed at "
                                f"{settings.LIVE_GUARD_PROBE_MULTIPLIER:.2f}x because "
                                f"{self.guard_probe_reason}"
                            )
                        except Exception as e:
                            logger.warning(f"[GuardedProbe] Could not mark {resolved_symbol} as probe: {e}")

                    if entry_mode == "EXPLORE":
                        try:
                            from strategy.cooldown_manager import cooldown_manager
                            cooldown_manager.set_probe(decision_id, True)
                            outcome_logger.update_intent(
                                decision_id,
                                entry_mode="EXPLORE",
                                probe_reason=probe_reason or "demo exploration",
                            )
                            logger.warning(
                                f"[DemoExplore] {resolved_symbol} {direction.name} marked as EXPLORE probe; "
                                f"reason={probe_reason or 'demo exploration'}"
                            )
                        except Exception as e:
                            logger.warning(f"[DemoExplore] Could not mark {resolved_symbol} as explore probe: {e}")

                    cmd = SizePositionCommand(
                        strategy_id="gqos_alpha_v1",
                        decision_id=decision_id,
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
                    self._cmd_bus.dispatch(MessageEnvelope.create(payload=cmd, version=1, run_id=self.run_id))
                
                logger.info("AlphaWorker: Sleeping 60s...")
                for _ in range(60):
                    if not self._running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in AlphaWorker loop: {e}")
                time.sleep(5)
