class GlobalRiskNetting:
    def __init__(self):
        pass
        
    def net_exposures(self, orders: list) -> dict:
        """
        Internal Crossing Engine.
        The fund is a single balance sheet, not multiple traders.
        Nets off Longs and Shorts across desks before hitting the external market.
        """
        net_positions = {}
        internal_crossed_volume = 0.0
        
        for order in orders:
            ticker = order['ticker']
            qty = order['quantity'] if order['direction'] == 'LONG' else -order['quantity']
            
            if ticker not in net_positions:
                net_positions[ticker] = 0.0
                
            # If positions are offsetting, we cross internally
            if (net_positions[ticker] > 0 and qty < 0) or (net_positions[ticker] < 0 and qty > 0):
                crossed_qty = min(abs(net_positions[ticker]), abs(qty))
                internal_crossed_volume += crossed_qty
                
            net_positions[ticker] += qty
            
        external_orders = []
        for ticker, net_qty in net_positions.items():
            if net_qty > 0:
                external_orders.append({'ticker': ticker, 'direction': 'LONG', 'quantity': net_qty})
            elif net_qty < 0:
                external_orders.append({'ticker': ticker, 'direction': 'SHORT', 'quantity': abs(net_qty)})
                
        return {
            'external_orders': external_orders,
            'internal_crossed_volume': internal_crossed_volume
        }
