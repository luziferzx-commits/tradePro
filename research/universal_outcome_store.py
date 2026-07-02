import numpy as np
import pandas as pd
import hashlib
import os

class UniversalOutcomeStore:
    @staticmethod
    def generate_uuid(row):
        # hash(feature_uuid + direction + horizon + sl_atr_mult + tp_atr_mult)
        s = f"{row['feature_uuid']}_{row['direction']}_{row['horizon']}_{row['sl_atr_mult']}_{row['tp_atr_mult']}"
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    @staticmethod
    def label_outcomes(df: pd.DataFrame, sl_atr_mult=1.0, tp_atr_mult=1.5, horizons=[5, 10, 20, 50]):
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        atrs = df['atr'].values
        feature_uuids = df['feature_uuid'].values
        symbols = df['symbol'].values
        years = df['year'].values
        
        n = len(df)
        results = []
        
        sl_dist = atrs * sl_atr_mult
        tp_dist = atrs * tp_atr_mult
        
        long_sl = closes - sl_dist
        long_tp = closes + tp_dist
        
        short_sl = closes + sl_dist
        short_tp = closes - tp_dist
        
        max_h = max(horizons)
        for i in range(n - max_h):
            if atrs[i] == 0: continue
            
            for h in horizons:
                # --- LONG ---
                long_res = "TIMEOUT"
                long_pnl_r = 0.0
                max_high = closes[i]
                min_low = closes[i]
                time_to_outcome = h
                
                for j in range(i + 1, i + 1 + h):
                    if highs[j] > max_high: max_high = highs[j]
                    if lows[j] < min_low: min_low = lows[j]
                    
                    if lows[j] <= long_sl[i]:
                        long_res = "LOSS"
                        long_pnl_r = -sl_atr_mult
                        time_to_outcome = j - i
                        break
                    if highs[j] >= long_tp[i]:
                        long_res = "WIN"
                        long_pnl_r = tp_atr_mult
                        time_to_outcome = j - i
                        break
                
                if long_res == "TIMEOUT":
                    long_pnl_r = (closes[i + h] - closes[i]) / sl_dist[i]
                
                mfe_r_long = (max_high - closes[i]) / sl_dist[i]
                mae_r_long = (closes[i] - min_low) / sl_dist[i]
                
                results.append({
                    'feature_uuid': feature_uuids[i],
                    'symbol': symbols[i],
                    'year': years[i],
                    'direction': 'LONG',
                    'horizon': h,
                    'sl_atr_mult': sl_atr_mult,
                    'tp_atr_mult': tp_atr_mult,
                    'result': long_res,
                    'pnl_r': float(long_pnl_r),
                    'mfe_r': float(mfe_r_long),
                    'mae_r': float(mae_r_long),
                    'time_to_outcome': int(time_to_outcome),
                    'cost_r': 0.1 # default
                })
                
                # --- SHORT ---
                short_res = "TIMEOUT"
                short_pnl_r = 0.0
                max_high_s = closes[i]
                min_low_s = closes[i]
                time_to_outcome_s = h
                
                for j in range(i + 1, i + 1 + h):
                    if highs[j] > max_high_s: max_high_s = highs[j]
                    if lows[j] < min_low_s: min_low_s = lows[j]
                    
                    if highs[j] >= short_sl[i]:
                        short_res = "LOSS"
                        short_pnl_r = -sl_atr_mult
                        time_to_outcome_s = j - i
                        break
                    if lows[j] <= short_tp[i]:
                        short_res = "WIN"
                        short_pnl_r = tp_atr_mult
                        time_to_outcome_s = j - i
                        break
                        
                if short_res == "TIMEOUT":
                    short_pnl_r = (closes[i] - closes[i + h]) / sl_dist[i]
                    
                mfe_r_short = (closes[i] - min_low_s) / sl_dist[i]
                mae_r_short = (max_high_s - closes[i]) / sl_dist[i]
                    
                results.append({
                    'feature_uuid': feature_uuids[i],
                    'symbol': symbols[i],
                    'year': years[i],
                    'direction': 'SHORT',
                    'horizon': h,
                    'sl_atr_mult': sl_atr_mult,
                    'tp_atr_mult': tp_atr_mult,
                    'result': short_res,
                    'pnl_r': float(short_pnl_r),
                    'mfe_r': float(mfe_r_short),
                    'mae_r': float(mae_r_short),
                    'time_to_outcome': int(time_to_outcome_s),
                    'cost_r': 0.1
                })
                
        outcomes_df = pd.DataFrame(results)
        if not outcomes_df.empty:
            outcomes_df['outcome_uuid'] = outcomes_df.apply(UniversalOutcomeStore.generate_uuid, axis=1)
            
        return outcomes_df

    @staticmethod
    def save_partitioned(df: pd.DataFrame, base_dir: str):
        if df.empty: return
        store_path = os.path.join(base_dir, 'data', 'outcome_store')
        os.makedirs(store_path, exist_ok=True)
        for (sym, yr), group in df.groupby(['symbol', 'year']):
            part_dir = os.path.join(store_path, f"symbol={sym}", f"year={yr}")
            os.makedirs(part_dir, exist_ok=True)
            file_path = os.path.join(part_dir, "universal_outcomes.parquet")
            
            cols = [
                'outcome_uuid', 'feature_uuid', 'symbol', 'direction', 'horizon', 
                'sl_atr_mult', 'tp_atr_mult', 'result', 'pnl_r', 'mfe_r', 'mae_r', 
                'time_to_outcome', 'cost_r'
            ]
            
            if os.path.exists(file_path):
                existing_df = pd.read_parquet(file_path)
                combined = pd.concat([existing_df, group[cols]]).drop_duplicates(subset=['outcome_uuid'])
                combined.to_parquet(file_path, index=False)
            else:
                group[cols].to_parquet(file_path, index=False)
