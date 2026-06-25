class RegimeScaler:
    def __init__(self):
        pass
        
    def get_regime_multiplier(self, market_regime: str, volatility_index: float) -> float:
        """
        Dynamically scales capital allocation based on macro environment.
        Capital breathes, it does not switch strictly on/off unless extreme.
        """
        multiplier = 1.0
        
        if market_regime == 'COMPRESSION':
            # Mean reversion is stable, survivor alpha thrives
            multiplier = 1.30 # +30% boost
        elif market_regime == 'NORMAL':
            multiplier = 1.00 # Baseline
        elif market_regime == 'VOLATILITY_SHOCK':
            # Market is dangerous, toxicity is high. Scale down, but don't hard freeze.
            multiplier = 0.25 # -75% exposure
            
        # Continuous adjustment based on real-time volatility
        # If volatility is unusually high for the regime, taper further
        if volatility_index > 2.0: # Normalized scale
            multiplier *= 0.5
            
        return multiplier
