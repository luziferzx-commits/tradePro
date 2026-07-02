class LiveRiskGovernance:
    def __init__(self, max_daily_loss_pct=0.05, max_slippage_multiplier=2.0, max_margin_usage=0.8):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_slippage_multiplier = max_slippage_multiplier
        self.max_margin_usage = max_margin_usage
        
        # State Machine: NORMAL -> RECOVERY -> HALTED
        self.current_state = 'NORMAL'
        
    def evaluate_telemetry(self, telemetry_data: dict) -> str:
        """
        Evaluates real-time telemetry and transitions the state machine.
        """
        daily_loss_pct = telemetry_data.get('daily_loss_pct', 0.0)
        slippage_ratio = telemetry_data.get('actual_vs_expected_slippage', 1.0)
        mt5_connected = telemetry_data.get('mt5_connected', True)
        margin_usage = telemetry_data.get('margin_usage', 0.0)
        
        volatility_spike = telemetry_data.get('volatility_spike', False)
        latency_drift_trend = telemetry_data.get('latency_drift_trend', False)
        consecutive_losses = telemetry_data.get('consecutive_losses', 0)
        
        # 1. HARD KILL CONDITIONS
        if not mt5_connected:
            self.current_state = 'HALTED_MT5_DISCONNECT'
        elif daily_loss_pct >= self.max_daily_loss_pct:
            self.current_state = 'HALTED_DAILY_LOSS'
        elif slippage_ratio >= self.max_slippage_multiplier:
            self.current_state = 'HALTED_SEVERE_SLIPPAGE'
        elif margin_usage >= self.max_margin_usage:
            self.current_state = 'HALTED_MARGIN_WARNING'
            
        if self.current_state.startswith('HALTED'):
            return self.current_state
            
        # 2. SOFT KILL CONDITIONS -> RECOVERY MODE
        if volatility_spike or latency_drift_trend or consecutive_losses >= 3:
            self.current_state = 'RECOVERY'
        else:
            self.current_state = 'NORMAL'
            
        return self.current_state
        
    def is_trading_allowed(self) -> bool:
        return not self.current_state.startswith('HALTED')
