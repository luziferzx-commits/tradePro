import numpy as np

class OMSCore:
    def __init__(self, risk_gate):
        self.risk_gate = risk_gate
        self.active_positions = {}
        
    def evaluate_order_intent(self, alpha_signal: dict) -> dict:
        """
        Takes raw alpha signal.
        OMS decides 'SHOULD we trade' by validating against Risk Gate and Exposure limits.
        """
        # Validate against risk gate state
        if not self.risk_gate.is_trading_allowed():
            return {
                'status': 'REJECTED',
                'reason': 'Risk Gate is CLOSED',
                'order': None
            }
            
        cluster_id = alpha_signal['cluster_id']
        direction = alpha_signal['direction']
        confidence = alpha_signal['confidence']
        
        # Exposure checks
        current_exposure = self.active_positions.get(cluster_id, 0.0)
        
        # Simple rule: if we already have max exposure, reject.
        if abs(current_exposure) >= alpha_signal['max_allowed_exposure']:
            return {
                'status': 'REJECTED',
                'reason': 'Max exposure reached for cluster',
                'order': None
            }
            
        # Create definitive Order Intent for the EMS
        order_intent = {
            'order_id': f"ORD_{cluster_id}_{np.random.randint(1000, 9999)}",
            'cluster_id': cluster_id,
            'direction': direction,
            'target_size': alpha_signal['target_size'],
            'urgency': 'HIGH' if confidence > 0.8 else 'NORMAL'
        }
        
        return {
            'status': 'APPROVED',
            'reason': 'Passed OMS Validation',
            'order': order_intent
        }
