class SlippageModel:
    def __init__(self):
        # Symbol multipliers to account for baseline liquidity differences
        self.symbol_multipliers = {
            "EURUSDm": 0.8,  # Deep liquidity
            "GBPUSDm": 1.2,
            "USDJPYm": 1.0,
            "XAUUSDm": 1.5,
            "XAGUSDm": 1.8,
            "US30m": 2.5,    # Thinner
            "BTCUSDm": 3.0   # Noisy/Thinner
        }
        
    def estimate_from_ohlcv(self, signal: dict) -> float:
        """
        Phase B Slippage Model: OHLCV + ATR based
        Slippage = ATR * volatility_factor * liquidity_pressure * symbol_multiplier
        Returns slippage in points/pips equivalent.
        """
        atr = signal.get('atr', 10.0)
        volatility_factor = signal.get('volatility_factor', 1.0)
        
        # Proxy for liquidity pressure: higher in fast moving trending regimes
        liquidity_pressure = 1.2 if signal.get('regime') == 'TRENDING' else 1.0
        
        symbol_mult = self.symbol_multipliers.get(signal['symbol'], 1.0)
        
        # Base slippage as a fraction of ATR (e.g., 5% of ATR)
        base_slippage = atr * 0.05
        
        slippage = base_slippage * volatility_factor * liquidity_pressure * symbol_mult
        return slippage
        
    def estimate_from_l2(self, signal: dict) -> float:
        """
        Phase B.2: Synthetic L2 / Broker spread history.
        Not implemented in Phase B.
        """
        raise NotImplementedError("L2 estimation reserved for Phase B.2")
