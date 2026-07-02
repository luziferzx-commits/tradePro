class MicrostructureGenerator:
    def __init__(self):
        self.active_hypotheses = []
        
    def generate_hypotheses(self, l2_state: dict, order_flow_state: dict) -> list:
        """
        Generates microstructural alpha signals based strictly on L2 and Flow data.
        """
        signals = []
        
        obi = l2_state.get('obi', 0.0)
        micro_div = l2_state.get('microprice', 0.0) - l2_state.get('midprice', 0.0)
        cvd = order_flow_state.get('cvd', 0.0)
        
        # 1. Liquidity Vacuum Alpha
        # e.g., thin ask side, price likely to rip upward with minimal flow
        if obi > 0.6: # Extremely heavy bids vs thin asks
            signals.append({'type': 'LIQUIDITY_VACUUM', 'direction': 'LONG', 'confidence': obi})
            
        # 2. Toxic Flow Detection
        # Extreme short-term flow pressure but price instantly reverses -> spoofing / toxicity
        # (Mocking detection logic)
        if order_flow_state.get('flow_pressure', 0) > 100 and l2_state.get('price_reversal', False):
            signals.append({'type': 'TOXIC_FLOW_REVERSAL', 'direction': 'SHORT', 'confidence': 0.8})
            
        # 3. Hidden Accumulation
        if order_flow_state.get('hidden_accumulation', False):
            signals.append({'type': 'HIDDEN_ACCUMULATION', 'direction': 'LONG', 'confidence': 0.75})
            
        # 5. Microprice Divergence
        # If Microprice > Midprice significantly, the bid liquidity is much heavier
        if micro_div > l2_state.get('spread', 0.1) * 0.5:
            signals.append({'type': 'MICROPRICE_DIVERGENCE', 'direction': 'LONG', 'confidence': 0.6})
            
        return signals
