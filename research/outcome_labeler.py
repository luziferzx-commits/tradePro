import numpy as np
import pandas as pd

class OutcomeLabeler:
    @staticmethod
    def label_outcomes(df: pd.DataFrame, sl_atr_mult=1.0, tp_atr_mult=1.5, horizons=[5, 10, 20, 50]):
        # Convert to numpy for fast processing
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        atrs = df['atr'].values
        
        n = len(df)
        
        # We will return a list of dictionaries, one per valid candle/direction/horizon
        # To save memory, we might just return the results aggregated or as a large DataFrame
        # Actually, it's better to build feature-outcome pairs row by row
        
        results = []
        
        # Pre-calculate entry, sl, tp arrays
        sl_dist = atrs * sl_atr_mult
        tp_dist = atrs * tp_atr_mult
        
        long_sl = closes - sl_dist
        long_tp = closes + tp_dist
        
        short_sl = closes + sl_dist
        short_tp = closes - tp_dist
        
        # Iterate over each row (skip the last max(horizons) rows)
        max_h = max(horizons)
        for i in range(n - max_h):
            if atrs[i] == 0: continue
            
            # For each horizon
            for h in horizons:
                # --- LONG ---
                long_res = "TIMEOUT"
                long_pnl_r = 0.0
                for j in range(i + 1, i + 1 + h):
                    if lows[j] <= long_sl[i]:
                        long_res = "LOSS"
                        long_pnl_r = -sl_atr_mult
                        break
                    if highs[j] >= long_tp[i]:
                        long_res = "WIN"
                        long_pnl_r = tp_atr_mult
                        break
                
                if long_res == "TIMEOUT":
                    # PnL at horizon close
                    long_pnl_r = (closes[i + h] - closes[i]) / sl_dist[i]
                
                results.append({
                    'index': i,
                    'direction': 'LONG',
                    'horizon': h,
                    'result': long_res,
                    'pnl_r': long_pnl_r
                })
                
                # --- SHORT ---
                short_res = "TIMEOUT"
                short_pnl_r = 0.0
                for j in range(i + 1, i + 1 + h):
                    if highs[j] >= short_sl[i]:
                        short_res = "LOSS"
                        short_pnl_r = -sl_atr_mult
                        break
                    if lows[j] <= short_tp[i]:
                        short_res = "WIN"
                        short_pnl_r = tp_atr_mult
                        break
                        
                if short_res == "TIMEOUT":
                    short_pnl_r = (closes[i] - closes[i + h]) / sl_dist[i]
                    
                results.append({
                    'index': i,
                    'direction': 'SHORT',
                    'horizon': h,
                    'result': short_res,
                    'pnl_r': short_pnl_r
                })
                
        return pd.DataFrame(results)
