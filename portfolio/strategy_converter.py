import pandas as pd
import numpy as np

class StrategyConverter:
    def __init__(self, atr_multiplier=2.0):
        self.atr_multiplier = atr_multiplier
        
        # Max hold times based on regime volatility
        self.time_decay_limits = {
            'LOW_VOL_COMPRESSION': 24, # e.g. 2 hours on M5
            'NORMAL_VOLATILITY': 12,   # 1 hour
            'HIGH_VOL_EXPANSION': 6    # 30 mins
        }

    def simulate_hypothesis(self, df: pd.DataFrame, condition_series: pd.Series, regime: str, direction: int) -> pd.Series:
        """
        Simulates the 3-Layer Exit System for a given hypothesis.
        direction: 1 (Buy) or -1 (Sell)
        Returns the series of trade returns (index aligned with entry) and a signal mask.
        """
        # Entry logic
        regime_mask = df['regime_label'] == regime
        entry_mask = regime_mask & condition_series
        
        returns = pd.Series(0.0, index=df.index)
        active_trade = False
        entry_price = 0.0
        entry_idx = 0
        entry_idx_num = 0
        sl_price = 0.0
        max_hold = self.time_decay_limits.get(regime, 12)
        
        # To iterate efficiently, we can use numpy arrays or simple loop.
        # Since M5 data is ~50k rows, simple loop might take a few seconds per hypothesis.
        # Let's vectorize where possible or just numba it if needed. For now, simple loop.
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        atrs = df['atr'].values if 'atr' in df.columns else np.zeros(len(df))
        regimes = df['regime_label'].values
        entries = entry_mask.values
        
        res_returns = np.zeros(len(df))
        
        for i in range(len(df)):
            if active_trade:
                bars_held = i - entry_idx_num
                current_regime = regimes[i]
                
                # Layer 1: Structural Exit (Regime changed)
                exit_layer1 = current_regime != regime
                
                # Layer 2: Time Decay Exit
                exit_layer2 = bars_held >= max_hold
                
                # Layer 3: Risk Exit (ATR Stop)
                hit_sl = False
                if direction == 1 and lows[i] <= sl_price:
                    hit_sl = True
                elif direction == -1 and highs[i] >= sl_price:
                    hit_sl = True
                    
                if exit_layer1 or exit_layer2 or hit_sl:
                    # Execute Exit
                    if hit_sl:
                        exit_price = sl_price
                    else:
                        exit_price = closes[i]
                        
                    trade_ret = (exit_price - entry_price) / entry_price * direction
                    res_returns[entry_idx_num] = trade_ret
                    active_trade = False
                    
            if not active_trade and entries[i]:
                # Enter trade
                active_trade = True
                entry_price = closes[i]
                entry_idx_num = i
                # Set initial SL
                if direction == 1:
                    sl_price = entry_price - (atrs[i] * self.atr_multiplier)
                else:
                    sl_price = entry_price + (atrs[i] * self.atr_multiplier)
                    
        return pd.Series(res_returns, index=df.index)

    def convert_all(self, df: pd.DataFrame, hypotheses: pd.DataFrame, condition_dict: dict) -> pd.DataFrame:
        """
        Converts the hypothesis library into a dataframe of equity curves (trade returns).
        """
        print("--- Converting Hypotheses to 3-Layer Exit Strategies ---")
        strategy_returns = {}
        
        for idx, row in hypotheses.iterrows():
            regime = row['regime']
            cond_name = row['condition']
            
            # Determine direction from the statistical expectation (Phase 5)
            direction = 1 if row['mean_return_bps'] > 0 else -1
            
            if cond_name not in condition_dict:
                continue
                
            cond_series = condition_dict[cond_name]
            
            # Simulate 3-Layer Exit
            rets = self.simulate_hypothesis(df, cond_series, regime, direction)
            strategy_name = f"ALPHA_{idx}_{regime}_{cond_name}"
            strategy_returns[strategy_name] = rets
            
        return pd.DataFrame(strategy_returns)
