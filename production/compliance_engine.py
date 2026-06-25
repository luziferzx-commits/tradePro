class ComplianceEngine:
    def __init__(self):
        self.restricted_list = ['TOXIC_TICKER_1', 'SUSPENDED_ASSET_2']
        self.max_gross_exposure = 5_000_000 # $5M hard cap
        self.max_leverage_cap = 1.0 # No margin allowed
        
    def check_order(self, order: dict, portfolio_state: dict, system_state: dict) -> dict:
        """
        Compliance sits ABOVE the Risk Engine. 
        It is a hard priority layer that overrides all quant logic.
        """
        # 1. Absolute Constraints
        if order['ticker'] in self.restricted_list:
            return {'status': 'REJECTED', 'reason': 'RESTRICTED_LIST'}
            
        proposed_gross = portfolio_state['current_gross'] + order['notional_value']
        if proposed_gross > self.max_gross_exposure:
            return {'status': 'REJECTED', 'reason': 'MAX_GROSS_EXPOSURE_EXCEEDED'}
            
        proposed_leverage = proposed_gross / portfolio_state['equity']
        if proposed_leverage > self.max_leverage_cap:
            return {'status': 'REJECTED', 'reason': 'MAX_LEVERAGE_EXCEEDED'}
            
        # 2. System-Level Constraints
        if system_state['correlation_spike'] > 0.85:
            return {'status': 'REJECTED', 'reason': 'SYSTEMIC_CORRELATION_SPIKE'}
            
        if system_state['liquidity_collapse']:
            return {'status': 'REJECTED', 'reason': 'LIQUIDITY_COLLAPSE_HALT'}
            
        return {'status': 'APPROVED', 'reason': 'COMPLIANCE_PASSED'}
