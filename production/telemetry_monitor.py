class TelemetryMonitor:
    def __init__(self):
        self.metrics = {}
        
    def update_telemetry(self, raw_data: dict):
        """
        Calculates Institutional Telemetry Metrics
        """
        # 1. Execution Layer
        expected_slip = raw_data.get('expected_slippage_pts', 0)
        actual_slip = raw_data.get('actual_slippage_pts', 0)
        slip_divergence = actual_slip / expected_slip if expected_slip > 0 else 1.0
        
        # 2. Risk Layer
        live_kelly = raw_data.get('live_kelly', 0.0)
        dd_velocity = raw_data.get('dd_velocity', 0.0) # Speed of drawdown in % per hour
        margin_stress = raw_data.get('margin_usage', 0.0) / 0.8 # Normalized to max threshold
        
        # 3. Alpha Layer
        edge_decay = raw_data.get('rolling_edge_bps', 0) - raw_data.get('historical_edge_bps', 0)
        
        self.metrics = {
            'execution_slippage_divergence': slip_divergence,
            'fill_ratio': raw_data.get('fill_ratio', 1.0),
            'avg_latency_ms': raw_data.get('latency_ms', 0),
            'risk_live_kelly_usage': live_kelly,
            'risk_dd_velocity': dd_velocity,
            'risk_margin_stress': margin_stress,
            'alpha_edge_decay_bps': edge_decay,
            'regime_mismatch_score': raw_data.get('regime_mismatch', 0.0)
        }
        
    def get_dashboard(self) -> dict:
        return self.metrics
