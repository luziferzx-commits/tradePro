from decimal import Decimal
from typing import Any

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import ReconciliationFillEvent
from gqos.common.enums import TradeDirection
from gqos.risk.events import ExecuteTradeCommand
from gqos.accounting.models import Position

class LiveTradingEngine:
    def __init__(
        self, 
        event_bus: Any, 
        cmd_bus: Any,
        oms: Any, 
        adapter: Any, 
        safety: Any, 
        persistence: Any,
        accounting: Any,
        portfolio: Any,
        halt_on_reconcile_mismatch: bool = None,
    ):
        self._event_bus = event_bus
        self._cmd_bus = cmd_bus
        self._oms = oms
        self._adapter = adapter
        self._safety = safety
        self._persistence = persistence
        self._accounting = accounting
        self._portfolio = portfolio

        # Opt-in safety: when True, a startup position mismatch against broker
        # truth halts trading and trips the kill switch for manual review.
        # Default (False) keeps the auto-sync-and-resume design: broker truth is
        # applied to the ledger and trading continues.
        if halt_on_reconcile_mismatch is None:
            try:
                from config.settings import settings
                halt_on_reconcile_mismatch = bool(getattr(settings, "HALT_ON_RECONCILE_MISMATCH", False))
            except Exception:
                halt_on_reconcile_mismatch = False
        self._halt_on_reconcile_mismatch = halt_on_reconcile_mismatch

        self.is_reconciled = False
        
        self._cmd_bus.register_handler(ExecuteTradeCommand, self._handle_execute_command)
        
    def start(self):
        print("Starting Live Trading Engine...")
        # 1. Load Snapshot
        restored = self._persistence.load_snapshot(self._accounting.state, self._portfolio.state)
        print(f"Loaded Ledger Snapshot: {restored}")
        
        # 2. Broker Truth Reconciliation
        self._reconcile_broker_truth()
        if hasattr(self._portfolio, "rebuild_cash_reservations_from_positions"):
            self._portfolio.rebuild_cash_reservations_from_positions(self._accounting.state.positions.values())
            print("Rebuilt portfolio cash-reservation ledger from reconciled accounting positions.")
        
    def _reconcile_broker_truth(self):
        try:
            actual_position_details = self._get_actual_position_details()
            actual_positions = {
                symbol: details["quantity"]
                for symbol, details in actual_position_details.items()
            }
        except Exception as e:
            print(f"Failed to fetch broker positions: {e}. HALTING.")
            self._safety.trigger("Failed to query broker on startup")
            return

        local_positions = {}
        for key, pos in self._accounting.state.positions.items():
            sym = pos.symbol
            qty = pos.quantity if pos.direction == TradeDirection.BUY else -pos.quantity
            local_positions[sym] = local_positions.get(sym, Decimal('0')) + qty

        mismatch = False

        all_symbols = set(actual_positions) | set(local_positions)

        for sym in all_symbols:
            actual_qty = actual_positions.get(sym, Decimal('0'))
            local_qty = local_positions.get(sym, Decimal('0'))

            if actual_qty != local_qty:
                mismatch = True
                diff = actual_qty - local_qty
                direction = TradeDirection.BUY if diff > 0 else TradeDirection.SELL

                print(f"MISMATCH on {sym}: Local={local_qty}, Broker={actual_qty}. Auto-reconciling...")

                evt = ReconciliationFillEvent(
                    symbol=sym,
                    direction=direction,
                    quantity=abs(diff),
                    execution_price=Decimal('0'),
                    reason=f"Broker Truth Override: Actual={actual_qty}, Local={local_qty}"
                )

                # Inject into accounting
                env = MessageEnvelope.create(payload=evt, version=1)
                self._event_bus.publish(env)
                self._set_reconciled_position(
                    sym,
                    actual_qty,
                    actual_position_details.get(sym, {}).get("average_price", Decimal('0')),
                )

        if mismatch:
            if self._halt_on_reconcile_mismatch:
                print("Reconciliation MISMATCH detected. Positions synced from broker, "
                      "but HALTING for manual review (HALT_ON_RECONCILE_MISMATCH=True).")
                self.is_reconciled = False
                self._safety.trigger("Startup position mismatch vs broker truth")
            else:
                print("Reconciliation complete. Positions synced from broker. Resuming.")
                self.is_reconciled = True
        else:
            print("Reconciliation Passed. System is fully synced.")
            self.is_reconciled = True

    def _get_actual_position_details(self):
        if hasattr(self._adapter, "get_actual_position_details"):
            return self._adapter.get_actual_position_details()
        return {
            symbol: {"quantity": quantity, "average_price": Decimal('0')}
            for symbol, quantity in self._adapter.get_actual_positions().items()
        }

    def _set_reconciled_position(
        self,
        symbol: str,
        actual_qty: Decimal,
        broker_average_price: Decimal = Decimal('0'),
    ) -> None:
        existing_items = [
            (key, pos)
            for key, pos in self._accounting.state.positions.items()
            if pos.symbol == symbol
        ]
        existing_pos = existing_items[0][1] if existing_items else None
        strategy_id = (
            existing_pos.strategy_id
            if existing_pos is not None
            else self._infer_reconciliation_strategy_id()
        )

        for key, _ in existing_items:
            self._accounting.state.positions.pop(key, None)

        if actual_qty == Decimal('0'):
            return

        direction = TradeDirection.BUY if actual_qty > 0 else TradeDirection.SELL
        quantity = abs(actual_qty)
        average_price = Decimal(str(broker_average_price))
        if existing_pos is not None and existing_pos.direction == direction:
            average_price = Decimal(str(broker_average_price)) or existing_pos.average_price

        self._accounting.state.positions[f"{strategy_id}_{symbol}"] = Position(
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            average_price=average_price,
        )

    def _infer_reconciliation_strategy_id(self) -> str:
        allocations = getattr(getattr(self._portfolio, "state", None), "allocations", {})
        if len(allocations) == 1:
            return next(iter(allocations))
        return getattr(self._accounting.state, "strategy_id", "global")
            
    def _handle_execute_command(self, envelope: MessageEnvelope[ExecuteTradeCommand]):
        cmd = envelope.payload
        
        if not self.is_reconciled:
            print("Trading Blocked: Not Reconciled.")
            return
            
        if not self._safety.check_new_order_allowed():
            print("Trading Blocked: Kill Switch Triggered.")
            return
            
        order_id = self._oms.create_order(
            cmd.symbol,
            cmd.direction,
            cmd.quantity,
            cmd.strategy_id,
            risk_allocation_id=getattr(cmd, "risk_allocation_id", ""),
            portfolio_allocation_id=getattr(cmd, "portfolio_allocation_id", ""),
            stop_loss=cmd.stop_loss or Decimal('0'),
            take_profit=cmd.take_profit or Decimal('0'),
        )
        
        # Submit to broker
        price = cmd.estimated_value / cmd.quantity if cmd.quantity > 0 else Decimal('0')
        
        # Check if the adapter supports sl/tp by inspecting its signature, or just pass as kwargs if supported
        try:
            self._adapter.submit_order(order_id, cmd.symbol, cmd.direction, cmd.quantity, price, stop_loss=cmd.stop_loss, take_profit=cmd.take_profit, decision_id=getattr(cmd, 'decision_id', ''))
        except TypeError:
            # Fallback for adapters that don't support SL/TP yet
            self._adapter.submit_order(order_id, cmd.symbol, cmd.direction, cmd.quantity, price)
        
    def save_state(self):
        self._persistence.save_snapshot(self._accounting.state, self._portfolio.state)

    def stop(self):
        print("Stopping Live Trading Engine...")
        self.save_state()
        self._adapter.stop()
        print("Engine stopped safely.")
