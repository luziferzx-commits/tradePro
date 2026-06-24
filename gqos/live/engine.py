from decimal import Decimal
from typing import Any

from gqos.messaging.bus import IEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import ReconciliationFillEvent
from gqos.common.enums import TradeDirection
from gqos.risk.events import ExecuteTradeCommand

class LiveTradingEngine:
    def __init__(
        self, 
        event_bus: IEventBus, 
        oms: Any, 
        adapter: Any, 
        safety: Any, 
        persistence: Any, 
        accounting: Any, 
        portfolio: Any
    ):
        self._event_bus = event_bus
        self._oms = oms
        self._adapter = adapter
        self._safety = safety
        self._persistence = persistence
        self._accounting = accounting
        self._portfolio = portfolio
        
        self.is_reconciled = False
        
        self._event_bus.subscribe(ExecuteTradeCommand, self._handle_execute_command)
        
    def start(self):
        print("Starting Live Trading Engine...")
        # 1. Load Snapshot
        restored = self._persistence.load_snapshot(self._accounting.state, self._portfolio.state)
        print(f"Loaded Ledger Snapshot: {restored}")
        
        # 2. Broker Truth Reconciliation
        self._reconcile_broker_truth()
        
    def _reconcile_broker_truth(self):
        try:
            actual_positions = self._adapter.get_actual_positions()
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
        
        for sym, actual_qty in actual_positions.items():
            local_qty = local_positions.get(sym, Decimal('0'))
            
            if actual_qty != local_qty:
                mismatch = True
                diff = actual_qty - local_qty
                
                direction = TradeDirection.BUY if diff > 0 else TradeDirection.SELL
                
                print(f"MISMATCH on {sym}: Local={local_qty}, Broker={actual_qty}. Generating ReconciliationFill.")
                
                # Emit reconciliation event
                evt = ReconciliationFillEvent(
                    symbol=sym,
                    direction=direction,
                    quantity=abs(diff),
                    execution_price=Decimal('0'), # Reconciliation price
                    reason=f"Broker Truth Override: Actual={actual_qty}, Local={local_qty}"
                )
                # In real life we'd inject a trade into accounting here
                
        if mismatch:
            print("Reconciliation required. Live trading remains blocked.")
            self._safety.trigger("Broker truth mismatch on startup")
            self.is_reconciled = False
        else:
            print("Reconciliation Passed. System is fully synced.")
            self.is_reconciled = True
            
    def _handle_execute_command(self, envelope: MessageEnvelope[ExecuteTradeCommand]):
        cmd = envelope.payload
        
        if not self.is_reconciled:
            print("Trading Blocked: Not Reconciled.")
            return
            
        if not self._safety.check_new_order_allowed():
            print("Trading Blocked: Kill Switch Triggered.")
            return
            
        order_id = self._oms.create_order(cmd.symbol, cmd.direction, cmd.quantity, cmd.strategy_id)
        
        # Submit to broker
        self._adapter.submit_order(order_id, cmd.symbol, cmd.direction, cmd.quantity, cmd.estimated_value / cmd.quantity if cmd.quantity > 0 else Decimal('0'))
        
    def save_state(self):
        self._persistence.save_snapshot(self._accounting.state, self._portfolio.state)

    def stop(self):
        print("Stopping Live Trading Engine...")
        self.save_state()
        self._adapter.stop()
        print("Engine stopped safely.")
