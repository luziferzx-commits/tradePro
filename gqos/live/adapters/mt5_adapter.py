import logging
import threading
import time
import math
import yaml
from typing import Callable, Dict, Optional
from decimal import Decimal
import MetaTrader5 as mt5

_mt5_lock = threading.Lock()

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import HeartbeatEvent, OrderStatus
from gqos.live.interfaces import IBrokerAdapter
from gqos.common.enums import TradeDirection
from config.settings import settings

logger = logging.getLogger(__name__)


def _symbol_config_for_broker_symbol(broker_symbol: str) -> dict:
    try:
        with open("config/symbols.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        aliases = cfg.get("symbol_aliases", {})
        reverse_aliases = {str(v): str(k) for k, v in aliases.items()}
        logical_symbol = reverse_aliases.get(broker_symbol, broker_symbol)
        return (cfg.get("symbols", {}) or {}).get(logical_symbol, {})
    except Exception as e:
        logger.warning(f"Could not load symbol config for {broker_symbol}: {e}")
        return {}

class MT5BrokerAdapter(IBrokerAdapter):
    def __init__(self, event_bus: IEventBus, oms_callback: Callable):
        self._event_bus = event_bus
        self._oms_callback = oms_callback
        self._market_closed_backoff = {}
        self._pending_orders = {}
        
        self._running = False
        self._thread = None
        self._heartbeat_interval = 1.0
        
        # MT5 Initialization is handled globally in GoldBot usually, 
        # but we assume it is already initialized and connected here.
        with _mt5_lock:
            terminal_info = mt5.terminal_info()
        if not terminal_info:
            logger.warning("MT5 terminal_info() failed. MT5 might not be initialized.")

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("MT5BrokerAdapter started.")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        logger.info("MT5BrokerAdapter stopped.")

    def get_actual_positions(self) -> Dict[str, Decimal]:
        """Queries MT5 for true positions to reconcile against GQOS Ledger"""
        return {
            symbol: details["quantity"]
            for symbol, details in self.get_actual_position_details().items()
        }

    def get_actual_position_details(self) -> Dict[str, Dict[str, Decimal]]:
        """Queries MT5 for true net positions plus broker open-price estimates."""
        positions = {}
        with _mt5_lock:
            mt5_positions = mt5.positions_get()
        if mt5_positions:
            for p in mt5_positions:
                # MT5 position volume is positive. We assign sign based on direction.
                qty = Decimal(str(p.volume))
                if p.type == mt5.POSITION_TYPE_SELL:
                    qty = -qty

                price_open = Decimal(str(getattr(p, "price_open", "0")))
                gross_qty = abs(qty)
                if p.symbol in positions:
                    current = positions[p.symbol]
                    prev_gross_qty = abs(current["quantity"])
                    new_gross_qty = prev_gross_qty + gross_qty
                    if new_gross_qty > Decimal('0'):
                        current["average_price"] = (
                            (current["average_price"] * prev_gross_qty)
                            + (price_open * gross_qty)
                        ) / new_gross_qty
                    current["quantity"] += qty
                else:
                    positions[p.symbol] = {
                        "quantity": qty,
                        "average_price": price_open,
                    }
        return positions

    def submit_order(self, order_id: str, symbol: str, direction: TradeDirection, quantity: Decimal, price: Decimal, stop_loss: Optional[Decimal] = None, take_profit: Optional[Decimal] = None, decision_id: str = ""):
        # 1. Resolve symbol (EURUSD -> EURUSDm)
        try:
            from data.mt5_client import mt5_client
            resolved_symbol = mt5_client.resolve_symbol(symbol)
        except Exception:
            resolved_symbol = symbol

        # 2. Check Backoff
        import time
        if resolved_symbol in self._market_closed_backoff:
            if time.time() < self._market_closed_backoff[resolved_symbol]:
                self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "Market closed (Backoff)")
                return
            else:
                del self._market_closed_backoff[resolved_symbol]

        # 3. Get symbol info
        with _mt5_lock:
            sym_info = mt5.symbol_info(resolved_symbol)
        if sym_info is None:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), f"Symbol {resolved_symbol} not found")
            return

        # 3. Validate broker/account state.
        vol_step = sym_info.volume_step
        with _mt5_lock:
            acc_info = mt5.account_info()
        if acc_info is None:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "No account info")
            return
        
        try:
            from strategy.cooldown_manager import cooldown_manager
            if cooldown_manager.is_probe(decision_id):
                try:
                    from gqos.ops.recovery_readiness import current_probe_multiplier
                    multiplier = min(1.0, max(float(settings.LIVE_GUARD_PROBE_MULTIPLIER), current_probe_multiplier()))
                except Exception:
                    multiplier = float(settings.LIVE_GUARD_PROBE_MULTIPLIER)
                logger.info(f"[PortfolioBudget] {resolved_symbol} PROBE MODE active, dynamic multiplier={multiplier:.2f}x")
            else:
                from gqos.risk.portfolio_budget import portfolio_budget
                multiplier = portfolio_budget.get_multiplier(resolved_symbol)
                logger.info(f"[PortfolioBudget] {resolved_symbol} multiplier={multiplier:.2f}x")
        except Exception as e:
            logger.warning(f"Failed to get portfolio budget multiplier or probe state: {e}")
            multiplier = 1.0
            
        if multiplier <= 0.0:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), f"PortfolioBudget: Symbol {resolved_symbol} paused (Multiplier=0x)")
            return
        
        with _mt5_lock:
            tick = mt5.symbol_info_tick(resolved_symbol)
        if tick is None:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "Symbol tick not found")
            return

        symbol_config = _symbol_config_for_broker_symbol(resolved_symbol)
        max_spread = symbol_config.get("max_spread_points")
        current_spread = getattr(sym_info, "spread", None)
        if max_spread is not None and current_spread is not None and float(current_spread) > float(max_spread):
            self._oms_callback(
                order_id,
                OrderStatus.REJECTED.value,
                Decimal('0'),
                Decimal('0'),
                f"Spread too high for {resolved_symbol}: {current_spread} > {max_spread}",
            )
            return
            
        # Execution MUST honor the quantity approved by the sizing pipeline.
        requested_volume = float(quantity)
        risk_multiplier = min(float(multiplier), 1.0)
        raw_volume = requested_volume * risk_multiplier

        if vol_step <= 0:
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), f"Invalid volume step for {resolved_symbol}: {vol_step}")
            return

        volume = math.floor(raw_volume / vol_step) * vol_step
        volume = round(volume, 8)
        
        min_vol = float(sym_info.volume_min)

        if volume < min_vol:
            if getattr(settings, "LIVE_MICRO_MODE", False):
                logger.warning(f"LIVE_MICRO_MODE: Forcing volume from {volume} to {min_vol}")
                volume = min_vol
            else:
                msg = f"Requested volume {raw_volume:.8f} (broker_vol={volume:.4f}) below broker minimum {min_vol}"
                logger.warning(f"[SizingGuard] REJECTED {resolved_symbol}: {msg}")
                self._oms_callback(
                    order_id,
                    OrderStatus.REJECTED.value,
                    Decimal('0'),
                    Decimal('0'),
                    msg,
                )
                return

        volume = min(float(sym_info.volume_max), volume)
        
        logger.info(
            f"[SizingGuard] {resolved_symbol} requested_volume={requested_volume:.4f} "
            f"multiplier={risk_multiplier:.2f} -> broker_volume={volume:.4f} "
            f"(step={vol_step}, min={sym_info.volume_min}, max={sym_info.volume_max})"
        )

        is_entry = bool(decision_id)
        
        # Resolve filling mode dynamically
        allowed_modes = getattr(sym_info, "filling_mode", 2)
        if allowed_modes & 1:
            best_filling = mt5.ORDER_FILLING_FOK
        elif allowed_modes & 2:
            best_filling = mt5.ORDER_FILLING_IOC
        else:
            best_filling = mt5.ORDER_FILLING_RETURN
        
        if getattr(settings, "USE_SMART_EXECUTION", False) and is_entry:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL_LIMIT
            trade_action = mt5.TRADE_ACTION_PENDING
            spread = tick.ask - tick.bid
            exec_price = tick.bid + (spread / 2.0)
            # Normalize to tick size
            tick_size = getattr(sym_info, "trade_tick_size", 0) or getattr(sym_info, "point", 0) or 0.00001
            exec_price = round(exec_price / tick_size) * tick_size
            
            # Shift SL and TP to maintain the same distance from the new exec_price
            price_delta = float(exec_price) - float(price)
            if stop_loss and float(stop_loss) > 0:
                stop_loss = Decimal(str(float(stop_loss) + price_delta))
            if take_profit and float(take_profit) > 0:
                take_profit = Decimal(str(float(take_profit) + price_delta))
                
            type_time = mt5.ORDER_TIME_GTC
            expiration = 0
            type_filling = best_filling
        else:
            order_type = mt5.ORDER_TYPE_BUY if direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL
            trade_action = mt5.TRADE_ACTION_DEAL
            exec_price = tick.ask if direction == TradeDirection.BUY else tick.bid
            
            # Ensure SL/TP are consistent with market order price too
            price_delta = float(exec_price) - float(price)
            if stop_loss and float(stop_loss) > 0:
                stop_loss = Decimal(str(float(stop_loss) + price_delta))
            if take_profit and float(take_profit) > 0:
                take_profit = Decimal(str(float(take_profit) + price_delta))
                
            type_time = mt5.ORDER_TIME_GTC
            expiration = 0
            type_filling = mt5.ORDER_FILLING_IOC if (allowed_modes & 2) else best_filling

        max_risk_pct = Decimal(str(getattr(settings, "MAX_REAL_RISK_PER_TRADE_PCT", 0.02)))
        if stop_loss and float(stop_loss) > 0 and max_risk_pct > 0:
            tick_size = Decimal(str(getattr(sym_info, "trade_tick_size", 0) or 0))
            tick_value = Decimal(str(getattr(sym_info, "trade_tick_value", 0) or 0))
            sl_distance = abs(Decimal(str(exec_price)) - Decimal(str(stop_loss)))
            if tick_size > 0 and tick_value > 0 and sl_distance > 0:
                risk_per_lot = (sl_distance / tick_size) * tick_value
                current_risk = Decimal(str(volume)) * risk_per_lot
                max_risk = Decimal(str(acc_info.balance)) * max_risk_pct
                if current_risk > max_risk:
                    capped_volume = math.floor(float(max_risk / risk_per_lot) / vol_step) * vol_step
                    capped_volume = round(capped_volume, 8)
                    if capped_volume < min_vol:
                        self._oms_callback(
                            order_id,
                            OrderStatus.REJECTED.value,
                            Decimal('0'),
                            Decimal('0'),
                            (
                                f"Risk cap would require volume {capped_volume:.8f}, "
                                f"below broker minimum {min_vol}"
                            ),
                        )
                        return
                    logger.warning(
                        f"[RiskCap] {resolved_symbol} reducing volume {volume} -> {capped_volume} "
                        f"to keep SL risk <= {float(max_risk_pct * 100):.2f}% "
                        f"(${float(max_risk):.2f})"
                    )
                    volume = capped_volume

        request = {
            "action": trade_action,
            "symbol": resolved_symbol,
            "volume": volume,
            "type": order_type,
            "price": float(exec_price),
            "sl": float(stop_loss) if stop_loss else 0.0,
            "tp": float(take_profit) if take_profit else 0.0,
            "deviation": 20,
            "magic": settings.MAGIC_NUMBER,
            "comment": (f"GQOS-{decision_id.split('-')[-1]}" if decision_id else order_id[:10]),
            "type_time": type_time,
        }
        outcome_fill_metadata = {
            "symbol": resolved_symbol,
            "direction": direction.name if hasattr(direction, "name") else str(direction),
            "volume": float(volume),
            "quantity": float(volume),
            "intended_price": float(price),
            "expected_entry_price": float(exec_price),
            "stop_loss_price": float(stop_loss) if stop_loss else None,
            "take_profit_price": float(take_profit) if take_profit else None,
            "tick_size": float(getattr(sym_info, "trade_tick_size", 0) or getattr(sym_info, "point", 0) or 0),
            "tick_value": float(getattr(sym_info, "trade_tick_value", 0) or 0),
            "contract_size": float(getattr(sym_info, "trade_contract_size", 0) or 0),
        }
        
        if trade_action == mt5.TRADE_ACTION_DEAL:
            request["type_filling"] = type_filling
            
        if type_time == mt5.ORDER_TIME_SPECIFIED:
            request["expiration"] = expiration

        import time
        start_time = time.time()
        logger.error(f"DEBUG: MT5 Request: {request}") # ADDED FOR DEBUGGING
        logger.error(f"DEBUG: MT5 Types: {{k: type(v) for k, v in request.items()}}") # ADDED FOR TYPES
        with _mt5_lock:
            result = mt5.order_send(request)
        exec_time_ms = (time.time() - start_time) * 1000.0

        if result is None or result.retcode not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, mt5.TRADE_RETCODE_DONE_PARTIAL):
            err_comment = getattr(result, 'comment', 'Unknown MT5 Error')
            
            if "Market closed" in err_comment or "Trade is disabled" in err_comment or (result and result.retcode in [10018, 10017]):
                self._market_closed_backoff[resolved_symbol] = time.time() + 3600 # 1 hour
                
            logger.error(f"[{decision_id}] MT5 order_send failed for {order_id}: {err_comment}")
            
            try:
                from gqos.common.structured_logger import log_structured_event
                log_structured_event(
                    event_type="TRADE_FAILED",
                    decision_id=decision_id,
                    symbol=resolved_symbol,
                    side=direction.name,
                    status="FAILED",
                    reason=err_comment
                )
            except Exception:
                pass
            self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), err_comment)
            return

        logger.info(f"[{decision_id}] MT5 Order Executed: {result.order} in {exec_time_ms:.1f}ms")
        
        if getattr(settings, "USE_SMART_EXECUTION", False) and is_entry:
            self._pending_orders[result.order] = {
                "order_id": order_id,
                "symbol": resolved_symbol,
                "direction": direction,
                "quantity": Decimal(str(volume)),
                "expiration": expiration,
                "decision_id": decision_id,
                "intended_price": Decimal(str(exec_price)),
                "outcome_fill_metadata": outcome_fill_metadata,
            }
            self._oms_callback(order_id, OrderStatus.ACK.value, Decimal('0'), Decimal('0'), "MT5 Limit Accepted")
            return

        filled_qty = Decimal(str(result.volume))
        filled_price = Decimal(str(result.price))
        if decision_id:
            try:
                from gqos.learning.outcome_logger import outcome_logger
                outcome_logger.on_trade_opened(
                    ticket=result.order,
                    decision_id=decision_id,
                    **{
                        **outcome_fill_metadata,
                        "volume": float(filled_qty),
                        "quantity": float(filled_qty),
                        "fill_price": float(filled_price),
                        "actual_entry_price": float(filled_price),
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to link ticket for outcome_logger: {e}")
            # Position monitor picks up the new ticket by polling; the adapter
            # has no direct reference to it, so there is nothing to notify here.
        try:
            from gqos.common.structured_logger import log_structured_event
            log_structured_event(
                event_type="TRADE_EXECUTED",
                decision_id=decision_id,
                symbol=resolved_symbol,
                side=direction.name,
                status="EXECUTED",
                reason="Order Filled",
                metadata={"ticket": result.order, "risk_pct": 1.0} # We use 1% risk
            )
        except Exception as e:
            logger.warning(f"[{decision_id}] Failed to emit structured log: {e}")
        
        # Log slippage
        try:
            from gqos.execution.slippage_tracker import slippage_tracker
            slippage_tracker.log_slippage(
                symbol=resolved_symbol,
                direction=direction,
                expected_price=exec_price,
                actual_price=float(filled_price),
                execution_time_ms=exec_time_ms,
                volume=float(filled_qty)
            )
        except Exception as e:
            logger.warning(f"Failed to log slippage: {e}")

        self._oms_callback(order_id, OrderStatus.ACK.value, Decimal('0'), Decimal('0'), "MT5 Accepted")
        self._oms_callback(order_id, "FILL", filled_qty, filled_price, f"MT5 Ticket: {result.order}")

    def cancel_order(self, order_id: str):
        """
        Cancels an existing pending order.
        Since we only issue Market Orders (IOC) right now, cancel is not technically used.
        """
        self._oms_callback(order_id, OrderStatus.REJECTED.value, Decimal('0'), Decimal('0'), "Cancel not supported for Market Orders")

    def _run_loop(self):
        while self._running:
            # Emit heartbeat
            hb = HeartbeatEvent(
                timestamp=time.time(),
                latency_ms=1.0, # Mock latency
                status="OK"
            )
            self._event_bus.publish(MessageEnvelope.create(payload=hb, version=1))
            
            try:
                # Cancel old pending limit orders (Smart Execution fallback)
                expiry_minutes = getattr(settings, "LIMIT_ORDER_EXPIRY_MINUTES", 5)
                if getattr(settings, "USE_SMART_EXECUTION", False) and expiry_minutes > 0:
                    with _mt5_lock:
                        orders = mt5.orders_get()
                    if orders:
                        now = int(time.time())
                        for order in orders:
                            # order.time_setup is the broker time (seconds since 1970) it was placed.
                            # We compare it against tick time of the symbol to be accurate.
                            with _mt5_lock:
                                sym_tick = mt5.symbol_info_tick(order.symbol)
                            if sym_tick and (sym_tick.time - order.time_setup > expiry_minutes * 60):
                                cancel_req = {
                                    "action": mt5.TRADE_ACTION_REMOVE,
                                    "order": order.ticket
                                }
                                with _mt5_lock:
                                    res = mt5.order_send(cancel_req)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    logger.info(f"Cancelled expired Limit Order {order.ticket} on {order.symbol}")
                                else:
                                    logger.warning(f"Failed to cancel expired Limit Order {order.ticket}: {res}")
            except Exception as e:
                logger.error(f"Error checking for expired limit orders: {e}")

            # Check for filled orders (since we use IOC/Market and now Pending Orders):
            if self._pending_orders:
                with _mt5_lock:
                    mt5_orders = mt5.orders_get()
                active_tickets = {o.ticket for o in mt5_orders} if mt5_orders else set()
                
                for ticket, data in list(self._pending_orders.items()):
                    if ticket not in active_tickets:
                        with _mt5_lock:
                            h_orders = mt5.history_orders_get(ticket=ticket)
                        if h_orders:
                            h_ord = h_orders[0]
                            if h_ord.state == mt5.ORDER_STATE_FILLED or h_ord.state == mt5.ORDER_STATE_PARTIAL:
                                filled_qty = Decimal(str(h_ord.volume_initial - h_ord.volume_current))
                                if filled_qty > 0:
                                    fill_price = Decimal(str(getattr(h_ord, "price_current", 0) or getattr(h_ord, "price_open", 0) or data["intended_price"]))
                                    try:
                                        from gqos.learning.outcome_logger import outcome_logger
                                        if data.get("decision_id"):
                                            metadata = dict(data.get("outcome_fill_metadata") or {})
                                            outcome_logger.on_trade_opened(
                                                ticket=ticket,
                                                decision_id=data["decision_id"],
                                                **{
                                                    **metadata,
                                                    "volume": float(filled_qty),
                                                    "quantity": float(filled_qty),
                                                    "fill_price": float(fill_price),
                                                    "actual_entry_price": float(fill_price),
                                                },
                                            )
                                    except Exception as e:
                                        logger.warning(f"Failed to link limit ticket for outcome_logger: {e}")
                                    try:
                                        from gqos.common.structured_logger import log_structured_event
                                        log_structured_event(
                                            event_type="TRADE_EXECUTED",
                                            decision_id=data.get("decision_id", ""),
                                            symbol=data["symbol"],
                                            side=data["direction"].name,
                                            status="EXECUTED",
                                            reason="Limit Order Filled",
                                            metadata={"ticket": ticket}
                                        )
                                    except Exception:
                                        pass
                                    self._oms_callback(data["order_id"], "FILL", filled_qty, fill_price, f"MT5 Limit Filled: {ticket}")
                                del self._pending_orders[ticket]
                            elif h_ord.state in (mt5.ORDER_STATE_EXPIRED, mt5.ORDER_STATE_CANCELED, mt5.ORDER_STATE_REJECTED):
                                self._oms_callback(data["order_id"], OrderStatus.EXPIRED.value, Decimal('0'), Decimal('0'), f"MT5 Limit {h_ord.state}")
                                del self._pending_orders[ticket]
                        else:
                            if time.time() > data["expiration"] + 60:
                                self._oms_callback(data["order_id"], OrderStatus.EXPIRED.value, Decimal('0'), Decimal('0'), "MT5 Limit assumed expired")
                                del self._pending_orders[ticket]

            time.sleep(self._heartbeat_interval)
