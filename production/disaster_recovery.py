class DisasterRecoverySystem:
    def __init__(self):
        self.automated_kill_switch_active = False
        self.risk_officer_override_active = False
        self.dead_mans_switch_active = False
        
    def evaluate_system_health(self, slippage: float, dd_speed: float, audit_chain_valid: bool, telemetry_status: str) -> dict:
        """
        3-Layer Override System.
        In institutional systems, failure must still produce orderliness.
        """
        actions = []
        
        # Layer 1: Automated Kill Switch
        if slippage > 0.05 or dd_speed > 5000.0:
            self.automated_kill_switch_active = True
            actions.append("LAYER_1_HALT_NEW_ORDERS")
            
        # Layer 3: System-Wide Dead Man's Switch
        # Triggers if we lose our eyes (telemetry) or our brain/memory (audit chain)
        if not audit_chain_valid or telemetry_status == 'OFFLINE':
            self.dead_mans_switch_active = True
            actions.append("LAYER_3_FORCE_FLATTEN_ALL_POSITIONS")
            
        return {
            'layer_1_active': self.automated_kill_switch_active,
            'layer_2_active': self.risk_officer_override_active, # Controlled externally via API
            'layer_3_active': self.dead_mans_switch_active,
            'actions': actions
        }
        
    def trigger_risk_officer_override(self):
        """
        Layer 2: Manual Halt
        """
        self.risk_officer_override_active = True
        return "LAYER_2_EMERGENCY_DELEVERAGE"
