import random
import time
from execution.fill_model import FillModel
from execution.slippage_model import SlippageModel
from execution.pnl_tracker import PaperPnlTracker

class PaperExecutor:
    def __init__(self):
        self.fill_model = FillModel()
        self.slippage_model = SlippageModel()
        self.pnl_tracker = PaperPnlTracker()
        
    def _simulate_latency(self, volatility: float) -> float:
        """
        Retail/VPS Realistic Latency (ms)
        """
        base_latency = 80.0
        jitter = random.uniform(20.0, 150.0)
        
        volatility_mult = 1.0
        if volatility > 1.5:
            volatility_mult = random.uniform(1.5, 2.5)
            
        return (base_latency + jitter) * volatility_mult

    def execute_order(self, signal: dict) -> dict:
        """
        Simulates the execution lifecycle: NEW → QUEUED → PARTIAL_FILL → FILLED
        Strictly DRY_RUN/PAPER_MODE.
        """
        # 1. NEW
        state = "NEW"
        
        # 2. QUEUED (Simulate Latency)
        state = "QUEUED"
        latency_ms = self._simulate_latency(signal.get('volatility_factor', 1.0))
        
        # 3. FILL SIMULATION
        fill_data = self.fill_model.simulate_fill(signal)
        
        if fill_data['is_partial']:
            state = "PARTIAL_FILL"
        else:
            state = "FILLED"
            
        # 4. SLIPPAGE CALCULATION
        # Slippage happens due to the latency and the liquidity conditions
        slippage = self.slippage_model.estimate_from_ohlcv(signal)
        
        # If chasing, add extra slippage
        if fill_data['policy'] == "CONTROLLED_CHASE":
            slippage *= 1.5 
            fill_data['fill_ratio'] = min(1.0, fill_data['fill_ratio'] + 0.3)
            state = "FILLED"
            
        # 5. PnL / EXPECTANCY TRACKING
        pnl_data = self.pnl_tracker.calculate_execution_cost(
            signal, slippage, latency_ms, fill_data['fill_ratio']
        )
        
        state = "CLOSED"
        
        return {
            'symbol': signal['symbol'],
            'direction': signal['direction'],
            'ideal_entry': signal['entry_price'],
            'executed_entry': signal['entry_price'] + slippage if signal['direction'] == 'BUY' else signal['entry_price'] - slippage,
            'fill_ratio': fill_data['fill_ratio'],
            'is_partial': fill_data['is_partial'],
            'policy_used': fill_data['policy'],
            'slippage_cost_bps': pnl_data['slippage_cost_bps'],
            'spread_cost_bps': pnl_data['spread_cost_bps'],
            'latency_ms': latency_ms,
            'base_edge_bps': pnl_data['base_edge_bps'],
            'net_expectancy_bps': pnl_data['net_expectancy_bps'],
            'verdict': pnl_data['verdict']
        }
