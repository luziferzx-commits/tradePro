class CapitalPhasingController:
    def __init__(self, initial_phase=1):
        self.current_phase = initial_phase
        self.tracking_error_history = []
        
    def log_execution_error(self, expected_slip: float, actual_slip: float):
        error = abs(actual_slip - expected_slip)
        self.tracking_error_history.append(error)
        
    def evaluate_promotion(self):
        """
        Evaluates whether the system is stable enough to promote to the next capital phase.
        Capital increases only if 'prediction error == execution error stable'
        """
        if len(self.tracking_error_history) < 100:
            return # Need more data
            
        recent_errors = self.tracking_error_history[-100:]
        avg_error = sum(recent_errors) / len(recent_errors)
        
        # If execution divergence is stable, promote
        if avg_error < 2.0: # Tolerance threshold (pts)
            if self.current_phase < 4:
                self.current_phase += 1
                self.tracking_error_history = [] # Reset for next phase
                return f"PROMOTED to Phase {self.current_phase}"
                
        return "MAINTAIN_PHASE"
        
    def get_max_lot_size(self) -> float:
        if self.current_phase == 1:
            return 0.0 # Shadow Live
        elif self.current_phase == 2:
            return 0.01 # Micro Lot Live
        elif self.current_phase == 3:
            return 0.30 # Scaled Risk (30%)
        else:
            return 1.0 # Full Deployment (100%)
