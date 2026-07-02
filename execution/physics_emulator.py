import pandas as pd
import numpy as np
from execution.slippage_model import SlippageModel
from execution.liquidity_impact import LiquidityImpactModel
from execution.fill_simulator import FillSimulator
from execution.latency_model import LatencyModel

class PhysicsEmulator:
    def __init__(self):
        self.slippage_model = SlippageModel()
        self.liquidity_model = LiquidityImpactModel()
        self.fill_sim = FillSimulator()
        self.latency_model = LatencyModel()

    def process_order(self, ideal_price: float, direction: int, order_size: float, 
                      market_volume: float, atr: float, vol_imbalance: float, vol_zscore: float) -> dict:
        """
        Takes an ideal order and applies physical constraints.
        Returns the actual execution details.
        """
        # 1. Latency: Price drifts before we even get to the broker
        latency_price = self.latency_model.simulate_latency_drift(ideal_price, atr, direction)
        
        # 2. Liquidity Cap: How much of our order is even allowed to hit the book?
        capped_size = self.liquidity_model.check_capacity(order_size, market_volume)
        if capped_size < order_size:
            # We wanted to trade more, but liquidity caps us
            pass
            
        # 3. Fill Uncertainty: Do we actually get filled on the capped size?
        fill_res = self.fill_sim.simulate_fill(capped_size, market_volume * 0.1) # Proxy depth as 10% of volume
        
        if fill_res['status'] == 'MISSED':
            return {
                'status': 'MISSED',
                'actual_price': 0.0,
                'filled_size': 0.0,
                'slippage_paid': 0.0,
                'market_impact_paid': 0.0
            }
            
        final_size = fill_res['filled_size']
        
        # 4. Slippage & Spread Expansion (on the latency price)
        slip_res = self.slippage_model.calculate_slippage(final_size, atr, vol_imbalance, vol_zscore)
        spread_cost = slip_res['spread_cost']
        slippage_pct = slip_res['slippage_pct']
        
        # Convert % slippage to price
        slippage_price = latency_price * slippage_pct
        
        # 5. Market Impact (We push the market against ourselves)
        market_impact_pct = self.liquidity_model.calculate_market_impact(final_size, market_volume)
        impact_price = latency_price * market_impact_pct
        
        # Calculate Final Actual Entry Price
        total_friction = spread_cost + slippage_price + impact_price
        
        if direction == 1:
            actual_price = latency_price + total_friction
        else:
            actual_price = latency_price - total_friction
            
        return {
            'status': fill_res['status'],
            'actual_price': actual_price,
            'filled_size': final_size,
            'slippage_paid': slippage_price + spread_cost,
            'market_impact_paid': impact_price
        }

    def simulate_equity_degradation(self, df: pd.DataFrame, strategy_returns: pd.Series, allocations: pd.Series) -> pd.DataFrame:
        """
        Simulate the "Truth Tax". Takes the ideal equity curve returns, applies execution physics, and outputs the realistic curve.
        For simplicity, we approximate the physics penalty on the return series.
        """
        print("--- Applying Execution Physics ---")
        realistic_returns = np.zeros(len(df))
        
        for i in range(len(df)):
            ideal_ret = strategy_returns.iloc[i]
            if ideal_ret == 0:
                continue
                
            # Grab context
            price = df['close'].iloc[i]
            atr = df['atr'].iloc[i] if 'atr' in df.columns else 0.001
            vol = df['tick_volume'].iloc[i] if 'tick_volume' in df.columns else 1000
            alloc = allocations.iloc[i]
            
            # Approximated order size (e.g. alloc * $10M portfolio)
            order_size = alloc * 10000000
            
            # Assume Long for metric purposes (penalty is symmetrical)
            direction = 1 
            vol_imbalance = 0.5 # proxy
            vol_zscore = 1.0 # proxy
            
            res = self.process_order(price, direction, order_size, vol, atr, vol_imbalance, vol_zscore)
            
            if res['status'] == 'MISSED':
                realistic_returns[i] = 0.0
            else:
                # The total friction reduces the ideal return
                # Friction as a % of price
                friction_pct = (res['slippage_paid'] + res['market_impact_paid']) / price
                
                # Assume exit has similar friction (double it)
                total_friction_pct = friction_pct * 2
                
                # Apply to ideal return
                real_ret = ideal_ret - total_friction_pct
                
                # Account for partial fills
                fill_ratio = res['filled_size'] / order_size if order_size > 0 else 0
                
                realistic_returns[i] = real_ret * fill_ratio
                
        return pd.Series(realistic_returns, index=df.index)
