class EMSRouter:
    def __init__(self, tick_volume_cap_pct=0.05):
        self.tick_volume_cap_pct = tick_volume_cap_pct
        
    def route_order(self, order_intent: dict, current_market_volume: float) -> list:
        """
        Takes an order intent from the OMS and decides HOW to execute it.
        If the order is too large for the current liquidity, it slices it.
        """
        target_size = order_intent['target_size']
        max_chunk_size = current_market_volume * self.tick_volume_cap_pct
        
        execution_plan = []
        
        if target_size <= max_chunk_size:
            # Send as a single limit/market order
            execution_plan.append({
                'chunk_id': f"{order_intent['order_id']}_1",
                'size': target_size,
                'type': 'MARKET' if order_intent['urgency'] == 'HIGH' else 'LIMIT'
            })
        else:
            # Slice the order (Simplified TWAP/VWAP mechanism)
            remaining = target_size
            chunk_num = 1
            while remaining > 0:
                chunk = min(remaining, max_chunk_size)
                execution_plan.append({
                    'chunk_id': f"{order_intent['order_id']}_{chunk_num}",
                    'size': chunk,
                    'type': 'VWAP_SLICE'
                })
                remaining -= chunk
                chunk_num += 1
                
        return execution_plan
