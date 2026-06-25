class ContagionIsolator:
    def __init__(self):
        pass
        
    def assess_fund_health(self, desk_performances: dict) -> dict:
        """
        Risk Contagion Isolator.
        Never kill the whole fund unless systemic coupling is detected.
        """
        actions = {}
        failing_desks = 0
        total_desks = len(desk_performances)
        
        for desk_id, metrics in desk_performances.items():
            dd_velocity = metrics.get('dd_velocity', 0)
            
            if dd_velocity > 5000:
                actions[desk_id] = 'HARD_ISOLATION' # Freeze desk capital
                failing_desks += 1
            elif dd_velocity > 1000:
                actions[desk_id] = 'SOFT_DEGRADATION' # Reduce allocation
            else:
                actions[desk_id] = 'NORMAL'
                
        # Systemic check
        if failing_desks >= (total_desks * 0.6): # If > 60% of desks are failing rapidly
            return {'systemic_shock': True, 'action': 'SYSTEMIC_KILL_SWITCH'}
            
        return {'systemic_shock': False, 'desk_actions': actions}
