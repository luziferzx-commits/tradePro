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
import json
import os
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

        # เก็บ edge ตอนเปิด per symbol (persisted so it survives a reboot)
        self._opening_edge_path = os.getenv(
            "GQOS_OPENING_EDGE_PATH",
            os.path.join("data", "learning", "opening_edges.json"),
        )
        self._opening_edge: dict = self._load_opening_edges()   # symbol → edge_score ตอนเปิด

        # pending flip: symbol → candle count รอ confirm
        self._pending_flip: dict = {}   # symbol → {"direction": str, "count": int}
        
        # track if a position has already been reduced due to news
        self._news_reduced: dict = {}   # symbol → bool
        
        self._emitted_store_path = os.getenv(
            "GQOS_EMITTED_CLOSE_DEALS_PATH",
            os.path.join("data", "learning", "emitted_close_deals.json"),
        )
        self._emitted_tickets: set = self._load_emitted_close_keys()

        # Position-hygiene features (all opt-in / off by default).
        try:
            from config.settings import settings as _s
            self._auto_close_disabled = bool(getattr(_s, "AUTO_CLOSE_DISABLED_SYMBOLS", False))
            self._max_position_age_hours = float(getattr(_s, "MAX_POSITION_AGE_HOURS", 0) or 0)
            self._capacity_alert_pct = float(getattr(_s, "POSITION_CAPACITY_ALERT_PCT", 0.9) or 0.9)
            self._max_open_positions = int(getattr(_s, "MAX_OPEN_POSITIONS", 0) or 0)
        except Exception:
            self._auto_close_disabled = False
            self._max_position_age_hours = 0.0
            self._capacity_alert_pct = 0.9
            self._max_open_positions = 0
        self._enabled_broker_symbols = self._load_enabled_broker_symbols()
        self._capacity_alerted = False

        # Reliable, poll-based trade-open Telegram alerts (the event-driven path
        # fires unreliably). Tracks tickets we've already alerted on.
        self._alerted_opens_path = os.getenv(
            "GQOS_ALERTED_OPENS_PATH",
            os.path.join("data", "learning", "alerted_opens.json"),
        )
        self._alerted_opens = self._load_alerted_opens()

        logger.info("PositionMonitor initialized.")

    def _load_alerted_opens(self) -> set:
        try:
            with open(self._alerted_opens_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(x) for x in data}
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not load alerted-opens store: {e}")
        return set()

    def _save_alerted_opens(self):
        try:
            directory = os.path.dirname(self._alerted_opens_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self._alerted_opens_path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._alerted_opens)[-3000:], f)
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not save alerted-opens store: {e}")

    def _alert_new_opens(self, positions):
        """Send a Telegram TRADE OPENED alert for positions not yet alerted."""
        changed = False
        for pos in positions:
            if getattr(pos, "magic", None) != self._magic:
                continue
            ticket = str(getattr(pos, "ticket", "") or "")
            if not ticket or ticket in self._alerted_opens:
                continue
            try:
                from notifications.telegram_notifier import notify_trade_executed
                side = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                notify_trade_executed(
                    symbol=str(getattr(pos, "symbol", "")),
                    direction=side,
                    lot=float(getattr(pos, "volume", 0.0) or 0.0),
                    entry=float(getattr(pos, "price_open", 0.0) or 0.0),
                    sl=float(getattr(pos, "sl", 0.0) or 0.0),
                    tp=float(getattr(pos, "tp", 0.0) or 0.0),
                    ticket=ticket,
                )
                logger.info(f"[PositionMonitor] Open alert sent for {pos.symbol} #{ticket}")
            except Exception as e:
                logger.warning(f"[PositionMonitor] Open alert failed for {ticket}: {e}")
            # Mark as handled even if the send failed, to avoid alert spam loops.
            self._alerted_opens.add(ticket)
            changed = True
        if changed:
            self._save_alerted_opens()

    def _seed_alerted_opens(self):
        """Mark already-open positions as alerted at startup so a restart does
        not re-announce positions that opened before the bot came up."""
        try:
            for pos in (mt5.positions_get() or []):
                if getattr(pos, "magic", None) == self._magic:
                    self._alerted_opens.add(str(getattr(pos, "ticket", "") or ""))
            self._save_alerted_opens()
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not seed alerted-opens: {e}")

    def _load_enabled_broker_symbols(self) -> set:
        """Broker symbols (e.g. EURUSDm) that are enabled for live trading."""
        try:
            import yaml
            with open("config/symbols.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            aliases = cfg.get("symbol_aliases", {})
            out = set()
            for logical, meta in (cfg.get("symbols", {}) or {}).items():
                if meta.get("enabled", False):
                    out.add(str(aliases.get(logical, logical)))
            return out
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not load enabled symbols: {e}")
            return set()

    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────

    def register_intent(self, decision_id: str, symbol: str, edge_score: float):
        self._opening_edge[symbol] = edge_score
        self._pending_flip.pop(symbol, None)
        self._save_opening_edges()
        logger.info(f"[PositionMonitor] Registered {symbol} opening edge={edge_score:.3f}")

    def start(self):
        self._seed_recent_closed_deals()
        self._seed_alerted_opens()
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
                
            # Prefer the persisted opening edge from before the reboot; only
            # re-derive from the current signal if we have nothing stored.
            if symbol in self._opening_edge:
                logger.info(f"[PositionMonitor Boot] {symbol} using persisted edge: {self._opening_edge[symbol]:.3f}")
                continue

            sig = self._evidence_router.evaluate(df, base_sym, log_events=False)
            if sig:
                confidence = float(sig.get("confidence", 0.5))
                self._opening_edge[symbol] = confidence
                self._save_opening_edges()
                logger.info(f"[PositionMonitor Boot] {symbol} assigned edge: {confidence:.3f}")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("PositionMonitor stopped.")

    def _load_emitted_close_keys(self) -> set:
        try:
            with open(self._emitted_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(item) for item in data}
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not load emitted close deal store: {e}")
        return set()

    def _save_emitted_close_keys(self):
        try:
            directory = os.path.dirname(self._emitted_store_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            keys = sorted(self._emitted_tickets)[-5000:]
            with open(self._emitted_store_path, "w", encoding="utf-8") as f:
                json.dump(keys, f)
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not save emitted close deal store: {e}")

    def _load_opening_edges(self) -> dict:
        try:
            with open(self._opening_edge_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                edges = {}
                for sym, val in data.items():
                    try:
                        edges[str(sym)] = float(val)
                    except (TypeError, ValueError):
                        continue
                if edges:
                    logger.info(f"[PositionMonitor] Loaded {len(edges)} persisted opening edges.")
                return edges
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not load opening edge store: {e}")
        return {}

    def _save_opening_edges(self):
        try:
            directory = os.path.dirname(self._opening_edge_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self._opening_edge_path, "w", encoding="utf-8") as f:
                json.dump({sym: float(edge) for sym, edge in self._opening_edge.items()}, f)
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not save opening edge store: {e}")

    def _remember_emitted_close(self, close_key):
        if close_key is None:
            return
        self._emitted_tickets.add(str(close_key))
        self._save_emitted_close_keys()

    def _remember_close_deal(self, deal):
        self._emitted_tickets.add(self._close_deal_key(deal))
        position_id = getattr(deal, "position_id", None)
        if position_id:
            self._emitted_tickets.add(str(position_id))
        self._save_emitted_close_keys()

    def _close_deal_key(self, deal):
        ticket = getattr(deal, "ticket", None)
        if ticket:
            return str(ticket)
        return str(getattr(deal, "position_id", ""))

    def _seed_recent_closed_deals(self):
        try:
            import datetime
            start = datetime.datetime.now() - datetime.timedelta(days=1)
            end = datetime.datetime.now() + datetime.timedelta(hours=1)
            deals = mt5.history_deals_get(start, end) or []
            seeded = 0
            for deal in deals:
                if (
                    getattr(deal, "magic", None) == self._magic
                    and getattr(deal, "entry", None) == mt5.DEAL_ENTRY_OUT
                ):
                    key = self._close_deal_key(deal)
                    if key and key not in self._emitted_tickets:
                        self._emitted_tickets.add(key)
                        position_id = getattr(deal, "position_id", None)
                        if position_id:
                            self._emitted_tickets.add(str(position_id))
                        seeded += 1
            if seeded:
                self._save_emitted_close_keys()
                logger.info(f"[PositionMonitor] Seeded {seeded} recent close deals to prevent restart duplicates.")
        except Exception as e:
            logger.warning(f"[PositionMonitor] Could not seed recent close deals: {e}")

    # ─────────────────────────────────────────────────────────────────
    # Main loop — รันทุก M5 candle
    # ─────────────────────────────────────────────────────────────────

    def _run_loop(self):
        last_candle_time = None
        while self._running:
            try:
                # ตรวจว่ามี M5 candle ใหม่ไหม
                positions = mt5.positions_get()
                if not positions:
                    time.sleep(5)
                    continue
                
                tick = mt5.symbol_info_tick(positions[0].symbol)
                if tick is None:
                    time.sleep(5)
                    continue

                current_minute = (tick.time // 300) * 300   # round to M5
                if current_minute == last_candle_time:
                    time.sleep(1)
                    continue

                if last_candle_time is not None:
                    self._check_new_deals(last_candle_time, tick.time)

                last_candle_time = current_minute
                self._evaluate_all_positions()

            except Exception as e:
                logger.error(f"[PositionMonitor] Error: {e}", exc_info=True)
                time.sleep(5)

    def _check_new_deals(self, from_time, to_time):
        if not hasattr(self, '_evt_bus') or not self._evt_bus:
            return
            
        import datetime
        # Use a wide 24-hour window based on local time to avoid MT5 timezone mismatch bugs
        # The _emitted_tickets set ensures we don't process duplicates
        start = datetime.datetime.now() - datetime.timedelta(days=1)
        end = datetime.datetime.now() + datetime.timedelta(hours=1)
        
        deals = mt5.history_deals_get(start, end)
        if not deals:
            return
            
        for d in deals:
            if d.magic == self._magic and d.entry == 1:
                deal_key = self._close_deal_key(d)
                position_key = str(getattr(d, "position_id", ""))
                if deal_key in self._emitted_tickets or position_key in self._emitted_tickets:
                    continue
                
                self._remember_close_deal(d)
                
                from gqos.accounting.events import RealizedPnLEmittedEvent
                from gqos.messaging.contracts import MessageEnvelope
                from decimal import Decimal
                
                logger.info(f"[PositionMonitor] 🚨 Detected MT5 Deal Close (SL/TP/Manual): {d.symbol} ticket={d.position_id} pnl={d.profit}")
                
                event = RealizedPnLEmittedEvent(
                    strategy_id="gqos_alpha_v1",
                    symbol=d.symbol,
                    realized_pnl=Decimal(str(d.profit)),
                    ticket=d.position_id,
                    exit_price=Decimal(str(d.price))
                )
                self._evt_bus.publish(MessageEnvelope.create(payload=event, version=1))
                
                self._opening_edge.pop(d.symbol, None)
                self._save_opening_edges()
                self._news_reduced.pop(d.symbol, None)

    # ─────────────────────────────────────────────────────────────────
    # Evaluate all open positions
    # ─────────────────────────────────────────────────────────────────

    def _evaluate_all_positions(self):
        positions = mt5.positions_get() or []
        if not positions:
            self._capacity_alerted = False
            return

        # Reliable trade-open alerts (poll-based, mirrors the close path).
        self._alert_new_opens(positions)

        # ─── Capacity alert: warn when position slots are nearly full ───
        mine = [p for p in positions if p.magic == self._magic]
        if self._max_open_positions > 0:
            threshold = self._capacity_alert_pct * self._max_open_positions
            if len(mine) >= threshold and not self._capacity_alerted:
                self._capacity_alerted = True
                msg = f"Position slots nearly full: {len(mine)}/{self._max_open_positions} — new entries may be blocked."
                logger.warning(f"[PositionMonitor] {msg}")
                try:
                    from notifications.telegram_notifier import send_telegram
                    send_telegram(f"⚠️ <b>Capacity</b>\n{msg}")
                except Exception as e:
                    logger.debug(f"capacity alert telegram failed: {e}")
            elif len(mine) < threshold:
                self._capacity_alerted = False

        # ─── Weekend Liquidation (Friday >= 22:45 UTC) ───
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        if now_utc.weekday() == 4 and now_utc.hour >= 22 and now_utc.minute >= 45:
            logger.warning("[PositionMonitor] 🚨 Friday 22:45 UTC reached! Liquidating all for weekend.")
            try:
                from notifications.telegram_notifier import send_telegram
                send_telegram("🚨 <b>Weekend Liquidation</b>\nFriday 22:45 UTC reached! Closing all active positions for the weekend.")
            except Exception:
                pass
            for pos in positions:
                if pos.magic == self._magic:
                    self._close_position(pos, reason="Weekend Close")
            return
        # ────────────────────────────────────────────────

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

        # #1 Auto-liquidate positions on symbols disabled for live trading.
        if self._auto_close_disabled and self._enabled_broker_symbols and symbol not in self._enabled_broker_symbols:
            logger.warning(f"[PositionMonitor] {symbol} is disabled for live trading — closing position.")
            self._close_position(pos, reason="Symbol disabled")
            return

        # #3 Close stale positions that have been open too long.
        if self._max_position_age_hours > 0:
            opened = getattr(pos, "time", 0) or 0
            if opened:
                age_h = (time.time() - float(opened)) / 3600.0
                if age_h >= self._max_position_age_hours:
                    logger.warning(f"[PositionMonitor] {symbol} open {age_h:.1f}h >= {self._max_position_age_hours}h — closing stale position.")
                    self._close_position(pos, reason=f"Stale > {self._max_position_age_hours}h")
                    return

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
        sig_now = self._evidence_router.evaluate(df, base_sym, log_events=False)

        opening_edge = self._opening_edge.get(symbol, 0.0)

        # ──── ตัดสินใจ ────────────────────────────────────────────────

        # Case: Capital Preservation (2R Breakeven)
        self._protect_profits(pos)

        # Case 0: High-Impact News coming?
        if self._news_filter and not self._news_reduced.get(symbol, False):
            if self._news_filter.is_high_impact_news_coming(symbol, within_minutes=30):
                logger.warning(
                    f"[PositionMonitor] {symbol}: High-Impact News approaching! CLOSING 100% position for safety (News Blackout)."
                )
                try:
                    from notifications.telegram_notifier import send_telegram
                    send_telegram(f"🚨 <b>News Blackout</b>\nHigh-impact news in < 30 mins. Force closing {symbol}.")
                except Exception:
                    pass
                self._close_position(pos, reason="News Blackout")
                self._news_reduced[symbol] = True
                return

        if opening_edge == 0:
            if sig_now is not None:
                opening_edge = float(sig_now.get("confidence", 0.5))
                self._opening_edge[symbol] = opening_edge
                self._save_opening_edges()
                logger.info(f"[PositionMonitor] {symbol}: Recovered opening edge as {opening_edge:.3f} on reboot")
            else:
                opening_edge = 0.5
                self._opening_edge[symbol] = opening_edge
                self._save_opening_edges()
                logger.info(f"[PositionMonitor] {symbol}: No active pattern on reboot, recovered with default opening edge = 0.500")

        # Case 1: No active signal
        if sig_now is None:
            logger.debug(f"[PositionMonitor] {symbol} {direction}: HOLD (No new signal)")
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
            self._save_opening_edges()
            return

        # Case 4: HOLD
        logger.debug(
            f"[PositionMonitor] {symbol} {direction}: HOLD "
            f"edge={edge_now:.3f} (open={opening_edge:.3f})"
        )

    # ─────────────────────────────────────────────────────────────────
    # MT5 Actions
    # ─────────────────────────────────────────────────────────────────

    def _learning_comment(self, pos, fallback: str) -> str:
        existing = str(getattr(pos, "comment", "") or "")
        if existing.upper().startswith("GQOS-"):
            return existing[:31]
        return fallback[:31]

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
            "comment":  self._learning_comment(pos, f"PM:{reason[:8]}"),
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[PositionMonitor] ✅ Closed {pos.symbol} | {reason}")
            self._opening_edge.pop(pos.symbol, None)
            self._save_opening_edges()
            self._news_reduced.pop(pos.symbol, None)
            if hasattr(self, '_initial_risk'):
                self._initial_risk.pop(pos.symbol, None)
            
            if hasattr(self, '_evt_bus') and self._evt_bus:
                try:
                    from gqos.accounting.events import RealizedPnLEmittedEvent
                    from gqos.messaging.contracts import MessageEnvelope
                    from decimal import Decimal
                    import time
                    
                    time.sleep(0.5)
                    deals = mt5.history_deals_get(position=pos.ticket)
                    realized_pnl = float(pos.profit)
                    exit_price = price
                    out_deal = None
                    
                    if deals:
                        out_deal = next((d for d in deals if d.entry == 1), None)
                        if out_deal:
                            realized_pnl = float(out_deal.profit)
                            exit_price = out_deal.price
                            
                    if out_deal:
                        self._remember_close_deal(out_deal)
                    else:
                        self._remember_emitted_close(pos.ticket)
                    event = RealizedPnLEmittedEvent(
                        strategy_id="gqos_alpha_v1",
                        symbol=pos.symbol,
                        realized_pnl=Decimal(str(realized_pnl)),
                        ticket=pos.ticket,
                        exit_price=Decimal(str(exit_price))
                    )
                    self._evt_bus.publish(MessageEnvelope.create(payload=event, version=1))
                except Exception as e:
                    logger.error(f"[PositionMonitor] Failed to emit RealizedPnLEmittedEvent: {e}")
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
            "comment":  self._learning_comment(pos, "PM:Reduce50"),
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
        self._save_opening_edges()

    def set_cmd_bus(self, cmd_bus):
        """inject cmd_bus สำหรับส่ง flip command"""
        self._cmd_bus = cmd_bus

    def set_event_bus(self, evt_bus):
        """inject evt_bus สำหรับส่ง RealizedPnLEmittedEvent"""
        self._evt_bus = evt_bus

    def _protect_profits(self, pos):
        """ถ้ากำไรถึง 2R ให้เลื่อน SL มาที่ Breakeven + 10 points และถ้าเกิน 3R ให้ Trailing 1.5R"""
        if pos.sl == 0.0:
            return

        if not hasattr(self, '_initial_risk'):
            self._initial_risk = {}

        if pos.symbol not in self._initial_risk:
            if pos.type == mt5.POSITION_TYPE_BUY:
                self._initial_risk[pos.symbol] = pos.price_open - pos.sl
            else:
                self._initial_risk[pos.symbol] = pos.sl - pos.price_open

        risk = self._initial_risk.get(pos.symbol, 0)
        if risk <= 0:
            return

        sym_info = mt5.symbol_info(pos.symbol)
        if not sym_info:
            return

        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick:
            return

        entry = pos.price_open
        current = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask

        if pos.type == mt5.POSITION_TYPE_BUY:
            profit = current - entry
            
            # Trailing Stop Check (>= 3R)
            if profit >= risk * 3.0:
                new_sl = current - (risk * 1.5)  # Trail by 1.5R distance
                if pos.sl < new_sl:
                    self._modify_sl(pos, new_sl, "Trailing Stop")
            # 2R Breakeven Check
            elif profit >= risk * 2.0:
                new_sl = entry + (sym_info.point * 10)
                if pos.sl < new_sl:
                    self._modify_sl(pos, new_sl, "Breakeven")
        else:
            profit = entry - current
            
            # Trailing Stop Check (>= 3R)
            if profit >= risk * 3.0:
                new_sl = current + (risk * 1.5)  # Trail by 1.5R distance
                if pos.sl == 0.0 or pos.sl > new_sl:
                    self._modify_sl(pos, new_sl, "Trailing Stop")
            # 2R Breakeven Check
            elif profit >= risk * 2.0:
                new_sl = entry - (sym_info.point * 10)
                if pos.sl == 0.0 or pos.sl > new_sl:
                    self._modify_sl(pos, new_sl, "Breakeven")

    def _modify_sl(self, pos, new_sl: float, reason: str):
        sym_info = mt5.symbol_info(pos.symbol)
        if not sym_info:
            return
            
        new_sl = round(new_sl, sym_info.digits)
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": float(pos.tp),
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"[PositionMonitor] ✅ SL Moved to {new_sl} for {pos.symbol} | {reason}")
            try:
                from notifications.telegram_notifier import send_telegram
                send_telegram(f"🛡 <b>{reason}</b>\nSL moved to <code>{new_sl}</code> for {pos.symbol}")
            except Exception:
                pass
        else:
            err = getattr(result, 'comment', 'Unknown') if result else 'None'
            logger.warning(f"[PositionMonitor] ❌ Move SL failed {pos.symbol}: {err}")
