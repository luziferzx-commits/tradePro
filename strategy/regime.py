import pandas as pd
import numpy as np

class RegimeClassifier:
    @staticmethod
    def calculate(df: pd.DataFrame) -> pd.DataFrame:
        """
        Classifies the market into distinct regimes:
        - TRENDING, RANGING, EXPANDING, CONTRACTING
        - Adds Regime-specific metrics like Volatility Percentile and Sweep Density.
        """
        if 'atr' not in df.columns or 'adx' not in df.columns:
            return df
            
        # 1. ATR Expansion
        df['atr_sma_50'] = df['atr'].rolling(50).mean()
        df['atr_expansion'] = df['atr'] / (df['atr_sma_50'] + 1e-9)
        
        # 2. Volatility Percentile (Fast Approximation over 500 periods ~ 2 Days on M5)
        atr_min_500 = df['atr'].rolling(500).min()
        atr_max_500 = df['atr'].rolling(500).max()
        df['vol_percentile'] = (df['atr'] - atr_min_500) / (atr_max_500 - atr_min_500 + 1e-9)
        
        # 3. Sweep Density (Choppy vs Runaway Trend)
        if 'sweep_swing_high_50' in df.columns and 'sweep_swing_low_50' in df.columns:
            sweeps = df['sweep_swing_high_50'].astype(int) + df['sweep_swing_low_50'].astype(int)
            df['sweep_density_50'] = sweeps.rolling(50).sum()
        else:
            df['sweep_density_50'] = 0
            
        # Ensure structural columns exist
        struct_trend = df['h1_struct_trend'] if 'h1_struct_trend' in df.columns else pd.Series(['NORMAL']*len(df), index=df.index)
        struct_strength = df['struct_strength'] if 'struct_strength' in df.columns else pd.Series(['NORMAL']*len(df), index=df.index)
            
        # 4. Regime Classification
        conditions = [
            # High volatility expansion
            (df['atr_expansion'] > 1.2) & (df['adx'] > 30), 
            
            # Trending
            (df['adx'] > 25) & (struct_strength == 'STRONG'),
            
            # Ranging
            (df['adx'] < 20) & (struct_trend == 'RANGING'),
            
            # Low volatility contraction
            (df['atr_expansion'] < 0.8) & (df['vol_percentile'] < 0.2),
            
            # Choppy (High sweeps but not strongly directional ADX)
            (df['sweep_density_50'] >= 2) & (df['adx'] < 25) & (struct_trend != 'RANGING')
        ]
        
        choices = ['EXPANDING', 'TRENDING', 'RANGING', 'CONTRACTING', 'CHOPPY_TREND']
        
        df['market_regime'] = np.select(conditions, choices, default='NORMAL')
        
        return df

regime_classifier = RegimeClassifier()
