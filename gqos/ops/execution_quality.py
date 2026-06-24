import json
import os
from decimal import Decimal
from typing import Dict
from gqos.common.enums import TradeDirection
from prometheus_client import Histogram, REGISTRY

# Initialize Prometheus Histogram for Slippage
SLIPPAGE_BPS = Histogram(
    'gqos_slippage_bps',
    'Execution slippage in basis points',
    ['symbol', 'direction']
)

class ExecutionQualityReport:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.filepath = os.path.join(self.log_dir, "execution_report.jsonl")
        
        # Track active orders
        self.active_orders: Dict[str, Dict] = {}
        
    def register_order(self, order_id: str, symbol: str, direction: TradeDirection, arrival_price: Decimal, quantity: Decimal):
        """Records the arrival price when an order is created."""
        self.active_orders[order_id] = {
            "symbol": symbol,
            "direction": direction,
            "arrival_price": arrival_price,
            "target_quantity": quantity,
            "filled_quantity": Decimal('0'),
            "filled_value": Decimal('0')
        }
        
    def record_fill(self, order_id: str, fill_qty: Decimal, fill_price: Decimal, is_final: bool = False):
        """Records a partial or complete fill and calculates VWAP slippage."""
        if order_id not in self.active_orders:
            return
            
        order = self.active_orders[order_id]
        order["filled_quantity"] += fill_qty
        order["filled_value"] += fill_qty * fill_price
        
        if is_final or order["filled_quantity"] >= order["target_quantity"]:
            # Calculate final VWAP
            if order["filled_quantity"] > 0:
                fill_vwap = order["filled_value"] / order["filled_quantity"]
                arrival_price = order["arrival_price"]
                
                # Calculate Slippage BPS
                if order["direction"] == TradeDirection.BUY:
                    slippage_bps = float((fill_vwap - arrival_price) / arrival_price * 10000)
                else:
                    slippage_bps = float((arrival_price - fill_vwap) / arrival_price * 10000)
                    
                # Export to Prometheus
                SLIPPAGE_BPS.labels(symbol=order["symbol"], direction=order["direction"].value).observe(slippage_bps)
                
                # Write to JSONL
                report_entry = {
                    "order_id": order_id,
                    "symbol": order["symbol"],
                    "direction": order["direction"].value,
                    "target_quantity": float(order["target_quantity"]),
                    "filled_quantity": float(order["filled_quantity"]),
                    "arrival_price": float(arrival_price),
                    "fill_vwap": float(fill_vwap),
                    "slippage_bps": slippage_bps
                }
                
                with open(self.filepath, 'a') as f:
                    f.write(json.dumps(report_entry) + "\n")
                    
            del self.active_orders[order_id]
