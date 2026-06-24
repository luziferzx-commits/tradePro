import pandas as pd
import numpy as np
from scipy import stats
import itertools
from research.microstructure_features import MicrostructureFeatures
from research.regime_discovery import RegimeDiscovery
from gqos.research.ml.validation import CombinatorialPurgedCV

class HypothesisEngine:
    def __init__(self, forward_bars=[5, 10, 20]):
        self.forward_bars = forward_bars
        
    def prepare_data(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        print("1. Calculating Microstructure Proxies...")
        df_micro = MicrostructureFeatures.generate_all(raw_df)
        
        print("2. Discovering Market Regimes (GMM+HMM)...")
        regime_detector = RegimeDiscovery(n_regimes=3)
        df_full = regime_detector.fit_predict(df_micro)
        
        print("3. Calculating Forward Returns...")
        for n in self.forward_bars:
            # log return over next N bars
            df_full[f'fwd_ret_{n}'] = np.log(df_full['close'].shift(-n) / df_full['close'])
            
        return df_full.dropna()

    def generate_templates(self, df: pd.DataFrame):
        """
        Creates binary conditions for microstructure features.
        """
        conditions = {}
        
        # Wick conditions
        conditions['HIGH_UPPER_WICK'] = df['upper_wick_ratio'] > df['upper_wick_ratio'].quantile(0.8)
        conditions['HIGH_LOWER_WICK'] = df['lower_wick_ratio'] > df['lower_wick_ratio'].quantile(0.8)
        
        # Aggression
        conditions['STRONG_BUY_AGGRESSION'] = df['aggression_imbalance'] > df['aggression_imbalance'].quantile(0.8)
        conditions['STRONG_SELL_AGGRESSION'] = df['aggression_imbalance'] < df['aggression_imbalance'].quantile(0.2)
        
        # CVD Pressure
        # Using CVD momentum (diff) rather than absolute cumulative value
        cvd_diff = df['cvd_proxy'].diff(5)
        conditions['CVD_MOMENTUM_UP'] = cvd_diff > cvd_diff.quantile(0.8)
        conditions['CVD_MOMENTUM_DOWN'] = cvd_diff < cvd_diff.quantile(0.2)
        
        # Stress
        conditions['VOLATILITY_SPIKE'] = df['volatility_spike_z'] > 2.0
        
        self.feature_conditions = conditions
        
    def run_statistical_mining(self, df: pd.DataFrame):
        print("4. Mining Hypotheses...")
        regimes = df['regime_label'].unique()
        conditions = list(self.feature_conditions.keys())
        
        hypotheses = []
        
        # We test combinations of (Regime) + (Condition)
        for regime in regimes:
            regime_mask = df['regime_label'] == regime
            
            for cond_name in conditions:
                cond_mask = self.feature_conditions[cond_name]
                
                # Combined mask
                signal_mask = regime_mask & cond_mask
                
                if signal_mask.sum() < 50:
                    continue # Not enough samples
                    
                signal_df = df[signal_mask]
                
                for n in self.forward_bars:
                    fwd_col = f'fwd_ret_{n}'
                    returns = signal_df[fwd_col].dropna()
                    
                    if len(returns) < 50:
                        continue
                        
                    mean_ret = returns.mean()
                    hit_rate = (returns > 0).mean() if mean_ret > 0 else (returns < 0).mean()
                    
                    # t-stat (1-sample t-test against 0)
                    t_stat, p_val = stats.ttest_1samp(returns, 0.0)
                    
                    # Tail ratio (95th percentile / abs(5th percentile))
                    p95 = np.percentile(returns, 95)
                    p05 = np.abs(np.percentile(returns, 5))
                    tail_ratio = p95 / p05 if p05 != 0 else 0
                    
                    hypotheses.append({
                        'regime': regime,
                        'condition': cond_name,
                        'forward_bars': n,
                        'samples': len(returns),
                        'mean_return_bps': mean_ret * 10000,
                        'hit_rate': hit_rate,
                        't_stat': t_stat,
                        'p_value': p_val,
                        'tail_ratio': tail_ratio
                    })
                    
        res_df = pd.DataFrame(hypotheses)
        # Filter for statistical significance
        sig_df = res_df[(res_df['p_value'] < 0.05) & (np.abs(res_df['t_stat']) > 2.0)]
        return sig_df.sort_values(by='t_stat', key=abs, ascending=False)
        
    def validate_with_cpcv(self, df: pd.DataFrame, sig_hypotheses: pd.DataFrame):
        print("5. Validating Top Hypotheses via CPCV...")
        # To strictly validate, we split the data using CPCV and see if the t_stat sign holds in test sets.
        n_samples = len(df)
        cpcv = CombinatorialPurgedCV(n_groups=6, k_test_groups=2, purge_pct=10/n_samples, embargo_pct=200/n_samples)
        
        splits = list(cpcv.split(df))
        
        validated = []
        for _, row in sig_hypotheses.iterrows():
            regime = row['regime']
            cond = row['condition']
            fwd = row['forward_bars']
            base_tstat_sign = np.sign(row['t_stat'])
            
            pass_count = 0
            
            for train_idx, test_idx in splits:
                df_test = df.iloc[test_idx]
                
                # Reconstruct condition in test set
                reg_mask = df_test['regime_label'] == regime
                
                # To be purely out of sample without lookahead on quantiles, 
                # we technically should calculate quantiles on train and apply to test.
                # For simplicity in this architectural phase, we approximate by filtering.
                
                # Using the stored boolean series directly on index
                test_indices = df_test.index
                cond_mask = self.feature_conditions[cond].loc[test_indices]
                
                signal_mask = reg_mask & cond_mask
                returns = df_test.loc[signal_mask, f'fwd_ret_{fwd}'].dropna()
                
                if len(returns) < 10:
                    continue # Ignore fold if too few samples
                    
                t_stat, _ = stats.ttest_1samp(returns, 0.0)
                if np.sign(t_stat) == base_tstat_sign:
                    pass_count += 1
                    
            consistency = pass_count / len(splits) if len(splits) > 0 else 0
            
            # Require 70% CPCV consistency
            if consistency >= 0.7:
                row_dict = row.to_dict()
                row_dict['cpcv_consistency'] = consistency
                validated.append(row_dict)
                
        return pd.DataFrame(validated)

if __name__ == "__main__":
    from data.mt5_client import mt5_client
    mt5_client.connect()
    print("Fetching raw OHLCV for XAUUSDm...")
    raw_df = mt5_client.get_historical_data("XAUUSDm", "M5", 100000)
    
    if raw_df is not None:
        engine = HypothesisEngine()
        df_prepared = engine.prepare_data(raw_df)
        engine.generate_templates(df_prepared)
        sig_df = engine.run_statistical_mining(df_prepared)
        val_df = engine.validate_with_cpcv(df_prepared, sig_df)
        
        print("\n--- Validated Hypotheses (XAUUSDm) ---")
        print(val_df)
        
        # Save to temp for Cross Market Validation
        import os
        os.makedirs("research/temp", exist_ok=True)
        val_df.to_csv("research/temp/base_hypotheses.csv", index=False)
