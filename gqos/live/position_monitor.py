"""
gqos/live/position_monitor.py

Dynamic Position Management
ประเมิน edge ของ open positions ทุก M5 candle ใหม่
และตัดสินใจ HOLD / REDUCE / CLOSE / FLIP อัตโนมัติ

Rules:
  HOLD        → edge ยังดีอยู่ (ทิศเดิม, score ไม่ตก)
  REDUCE 50%  → edge ลดลงเกิน 50% จากตอนเปิด
  CLOSE       → หมด edge (EvidenceRouter return None)
  FLIP        → ทิศกลับ → รอ 1 candle confirm แล้วค่อย flip
"""
import logging
import threading
import time
from decimal import Decimal
from typing import Optional
from datetime import datetime

import MetaTrader5 as mt5

logger = logging.getLogger("GQOS.PositionMonitor")


class PositionMonitor:
    def __init__(
        self,
        evidence_router,
        mt5_client,
        indicator_calculator,
        magic_number: int = 234000,
        reduce_threshold: float = 0.50,   # ลดเมื่อ edge เหลือ < 50% ของตอนเปิด
        flip_confirm_candles: int = 1,    # รอ 1 candle confirm ก่อน flip
        news_filter = None,               # News Filter for proactive risk management
    ):
        self._evidence_router    = evidence_router
        self._mt5_client         = mt5_client
        self._indicator_calc     = indicator_calculator
        self._magic              = magic_number
        self._reduce_threshold   = reduce_threshold
        self._flip_confirm       = flip_confirm_candles
        self._news_filter        = news_filter

        self._running   = False
        self._thread    = None

        # เก็บ edge ตอนเปิด per symbol
        self._opening_edge: dict = {}   # symbol → edge_score ตอนเปิด

        # pending flip: symbol → candle count รอ confirm
        self._pending_flip: dict = {}   # symbol → {"direction": str, "count": int}
        
        # track if a position has already been reduced due to news
        self._news_reduced: dict = {}   # symbol → bool

        logger.info("PositionMonitor initialized.")

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def register_open(self, symbol: str, edge_score: float):
        """เรียกเมื่อเปิด position ใหม่ — บันทึก edge ตอนเปิด"""
        self._opening_edge[symbol] = edge_score
        self._pending_flip.pop(symbol, None)
        logger.info(f"[PositionMonitor] Registered {symbol} opening edge={edge_score:.3f}")

    def start(self):
        self._re_evaluate_existing_positions()
        self._running = True
        self._thread  = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("PositionMonitor started.")

    def _re_evaluate_existing_positions(self):
        positions = mt5.positions_get()
        if not positions:
            return
            
        logger.info(f"Re-evaluating {len(positions)} existing positions on boot...")
        for pos in positions:
            if pos.magic != self._magic:
                continue
                
            symbol = pos.symbol
            base_sym = symbol.replace("m", "").replace(".m", "")
            
            df = self._mt5_client.get_historical_data(base_sym, "M15", 250)
            if df is None or df.empty:
                continue
                
            try:
                from strategy.indicators import IndicatorCalculator
                df = IndicatorCalculator.add_indicators(df)
            except Exception:
                pass
                
            sig = self._evidence_router.evaluate(df, base_sym)
            if sig:
                confidence = float(sig.get("confidence", 0.5))
                self._opening_edge[symbol] = confidence
                logger.info(f"[PositionMonitor Boot] {symbol} assigned edge: {confidence:.3f}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("PositionMonitor stopped.")

    # ─────────────────────────────────────────────────────────────────
    # Main loop — รันทุก M5 candle
    # ─────────────────────────────────────────────────────────────────

    def _run_loop(self):
        last_candle_time = None
        while self._running:
            try:
                # ตรวจว่ามี M5 candle ใหม่ไหม
                tick = mt5.symbol_info_tick("XAUUSDm") or mt5.symbol_info_tick("EURUSDm")
                if tick is None:
                    time.sleep(5)
                    continue

                current_minute = (tick.time // 300) * 300   # round to M5
                if current_minute == last_candle_time:
                    time.sleep(1)
                    continue

                last_candle_time = current_minute
                self._evaluate_all_positions()

            except Exception as e:
                logger.error(f"[PositionMonitor] Error: {e}", exc_info=True)
                time.sleep(5)

    # ─────────────────────────────────────────────────────────────────
    # Evaluate all open positions
    # ─────────────────────────────────────────────────────────────────

    def _evaluate_all_positions(self):
        positions = mt5.positions_get() or []
        if not positions:
            return

        for pos in positions:
            if pos.magic != self._magic:
                continue
            try:
                self._evaluate_single(pos)
            except Exception as e:
                logger.error(f"[PositionMonitor] Error evaluating {pos.symbol}: {e}")

    def _evaluate_single(self, pos):
        symbol    = pos.symbol
        base_sym  = symbol.replace("m", "").replace(".m", "")
        direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"

        # ดึงข้อมูลล่าสุด
        df = self._mt5_client.get_historical_data(base_sym, "M15", 250)
        if df is None or df.empty:
            return

        try:
            from strategy.indicators import IndicatorCalculator
            df = IndicatorCalculator.add_indicators(df)
        except Exception:
            pass

        # ประเมิน edge ใหม่
        sig_now = self._evidence_router.evaluate(df, base_sym)

        opening_edge = self._opening_edge.get(symbol, 0.0)

        # ──── ตัดสินใจ ────────────────────────────────────────────────

        # Case 0: High-Impact News coming?
        if self._news_filter and not self._news_reduced.get(symbol, False):
            if self._news_filter.is_high_impact_news_coming(symbol, within_minutes=30):
                logger.warning(
                    f"[PositionMonitor] {symbol}: High-Impact News approaching! REDUCING position 50% for safety."
                )
                self._reduce_position(pos, ratio=0.5)
                self._news_reduced[symbol] = True
                return

        if opening_edge == 0:
            logger.debug(f"[PositionMonitor] {symbol}: Unknown opening edge → HOLD")
            return

        # Case 1: หมด edge
        if sig_now is None:
            logger.info(f"[PositionMonitor] {symbol}: No edge → CLOSE")
            self._close_position(pos, reason="No edge")
            return

        edge_now  = float(sig_now.get("confidence", 0.5))
        dir_now   = sig_now.get("direction", "")   # "LONG" or "SHORT"
        dir_map   = {"LONG": "BUY", "SHORT": "SELL"}
        dir_clean = dir_map.get(dir_now, dir_now)

        # Case 2: ทิศกลับ → รอ 1 candle confirm
        if dir_clean != direction:
            pending = self._pending_flip.get(symbol)

            if pending is None:
                # บันทึก pending flip รอ confirm
                self._pending_flip[symbol] = {"direction": dir_clean, "count": 1}
                logger.info(
                    f"[PositionMonitor] {symbol}: Direction flip signal "
                    f"{direction}→{dir_clean}. Waiting 1 candle confirm..."
                )
            else:
                if pending["direction"] == dir_clean:
                    pending["count"] += 1
                    if pending["count"] >= self._flip_confirm:
                        # Confirmed → FLIP
                        logger.info(
                            f"[PositionMonitor] {symbol}: FLIP confirmed "
                            f"{direction}→{dir_clean}"
                        )
                        self._flip_position(pos, dir_clean, edge_now)
                        self._pending_flip.pop(symbol, None)
                    else:
                        logger.info(
                            f"[PositionMonitor] {symbol}: Waiting confirm "
                            f"{pending['count']}/{self._flip_confirm}"
                        )
                else:
                    # ทิศกลับซ้ำ reset
                    self._pending_flip.pop(symbol, None)
                    logger.info(f"[PositionMonitor] {symbol}: Flip signal cancelled")
            return

        # ทิศเดิม → reset pending flip
        self._pending_flip.pop(symbol, None)

        # Case 3: edge ลดลง > 50% → REDUCE
        if opening_edge > 0 and edge_now < opening_edge * self._reduce_threshold:
            logger.info(
                f"[PositionMonitor] {symbol}: Edge dropped "
                f"{opening_edge:.3f}→{edge_now:.3f} → REDUCE 50%"
            )
            self._reduce_position(pos, ratio=0.5)
            # อัปเดต opening_edge หลัง reduce
            self._opening_edge[symbol] = edge_now
            return

        # Case 4: HOLD
        logger.debug(
            f"[PositionMonitor] {symbol} {direction}: HOLD "
            f"edge={edge_now:.3f} (open={opening_edge:.3f})"
        )

    # ─────────────────────────────────────────────────────────────────
    # MT5 Actions
    # ─────────────────────────────────────────────────────────────────

    def _close_position(self, pos, reason: str = ""):
        """ปิด position ทั้งหมด"""
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY \
                     else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return

        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   pos.symbol,
            "volume":   pos.volume,
            "type":     close_type,
            "position": pos.ticket,
            "price":    price,
            "deviation": 20,
            "magic":    self._magic,
            "comment":  f"PM:{reason[:8]}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[PositionMonitor] ✅ Closed {pos.symbol} | {reason}")
            self._opening_edge.pop(pos.symbol, None)
            self._news_reduced.pop(pos.symbol, None)
        else:
            err = getattr(result, 'comment', 'Unknown') if result else 'None'
            logger.error(f"[PositionMonitor] ❌ Close failed {pos.symbol}: {err}")

    def _reduce_position(self, pos, ratio: float = 0.5):
        """ปิดบางส่วน (partial close)"""
        sym_info = mt5.symbol_info(pos.symbol)
        if sym_info is None:
            return

        reduce_vol = round(pos.volume * ratio, 2)
        reduce_vol = max(sym_info.volume_min, reduce_vol)

        if reduce_vol >= pos.volume:
            self._close_position(pos, reason="Reduce=Close")
            return

        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY \
                     else mt5.ORDER_TYPE_BUY
        tick  = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

        request = {
            "action":   mt5.TRADE_ACTION_DEAL,
            "symbol":   pos.symbol,
            "volume":   reduce_vol,
            "type":     close_type,
            "position": pos.ticket,
            "price":    price,
            "deviation": 20,
            "magic":    self._magic,
            "comment":  "PM:Reduce50",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"[PositionMonitor] ✅ Reduced {pos.symbol} "
                f"{pos.volume}→{pos.volume - reduce_vol:.2f} lots"
            )
        else:
            err = getattr(result, 'comment', 'Unknown') if result else 'None'
            logger.error(f"[PositionMonitor] ❌ Reduce failed {pos.symbol}: {err}")

    def _flip_position(self, pos, new_direction: str, edge_score: float):
        """ปิด position เดิม แล้วเปิดฝั่งตรงข้าม"""
        # Step 1: ปิดก่อน
        self._close_position(pos, reason="Flip")

        # Step 2: เปิดใหม่ฝั่งตรงข้าม
        from gqos.common.enums import TradeDirection
        from gqos.sizing.events import SizePositionCommand
        from gqos.messaging.contracts import MessageEnvelope

        direction = TradeDirection.BUY if new_direction == "BUY" else TradeDirection.SELL
        sym_info  = mt5.symbol_info(pos.symbol)
        if sym_info is None:
            return

        tick       = mt5.symbol_info_tick(pos.symbol)
        entry      = Decimal(str(tick.ask if direction == TradeDirection.BUY else tick.bid))
        atr        = Decimal(str(sym_info.point * 100))   # fallback
        sl_buffer  = atr * 3
        sl_price   = entry - sl_buffer if direction == TradeDirection.BUY \
                     else entry + sl_buffer
        tp_price   = entry + sl_buffer * 2 if direction == TradeDirection.BUY \
                     else entry - sl_buffer * 2

        cmd = SizePositionCommand(
            strategy_id="gqos_alpha_v1",
            symbol=pos.symbol,
            direction=direction,
            entry_price=entry,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            conviction=Decimal(str(edge_score)),
            metrics=None,
            volatility=None,
        )

        if self._cmd_bus:
            self._cmd_bus.dispatch(MessageEnvelope.create(payload=cmd, version=1))
            logger.info(
                f"[PositionMonitor] 🔄 Flipped {pos.symbol} → {new_direction} "
                f"entry={entry}"
            )

        self._opening_edge[pos.symbol] = edge_score

    def set_cmd_bus(self, cmd_bus):
        """inject cmd_bus สำหรับส่ง flip command"""
        self._cmd_bus = cmd_bus
