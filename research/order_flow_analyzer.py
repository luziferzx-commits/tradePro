class OrderFlowAnalyzer:
    def __init__(self):
        self.cumulative_flow_pressure = 0.0
        
    def analyze_trade_tape(self, aggressive_buy_vol: float, aggressive_sell_vol: float) -> dict:
        """
        Calculates instantaneous flow pressure and tracks accumulation over time.
        """
        flow_pressure = aggressive_buy_vol - aggressive_sell_vol
        self.cumulative_flow_pressure += flow_pressure
        
        return {
            'flow_pressure': flow_pressure,
            'cvd': self.cumulative_flow_pressure # Cumulative Volume Delta
        }
        
    def detect_hidden_accumulation(self, price_change: float, cvd_change: float) -> bool:
        """
        Hidden Accumulation:
        Price is relatively flat or dropping slightly, but CVD is persistently rising.
        This implies passive sellers are absorbing flow, or institutional buyers are iceberg-ing.
        """
        # If CVD goes up strongly but price doesn't follow
        if cvd_change > 0 and price_change <= 0:
            return True
        return False
