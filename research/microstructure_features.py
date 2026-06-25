import pandas as pd
import numpy as np

class MicrostructureFeatures:
    @staticmethod
    def calculate_cvd_proxy(df: pd.DataFrame) -> pd.Series:
        """
        CVD Proxy (Volume Pressure)
        CVD_t = Volume_t * sign(Close - Open)
        """
        if 'tick_volume' not in df.columns:
            return pd.Series(0, index=df.index)
            
        sign = np.sign(df['close'] - df['open'])
        # If open == close, we can use the previous sign or 0. We'll use 0.
        cvd_step = df['tick_volume'] * sign
        return cvd_step.cumsum()
        
    @staticmethod
    def calculate_aggression_imbalance(df: pd.DataFrame, period=14) -> pd.Series:
        """
        Aggression Imbalance
        AI = ((Close - Low) - (High - Close)) / ATR
        """
        # Need ATR. If not present, calculate a simple rolling ATR proxy
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        # Avoid division by zero
        atr = atr.replace(0, np.nan)
        
        ai = ((df['close'] - df['low']) - (df['high'] - df['close'])) / atr
        return ai.fillna(0)
        
    @staticmethod
    def calculate_wick_pressure(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """
        Wick Pressure
        UpperWickRatio = (High - max(Open, Close)) / ATR
        LowerWickRatio = (min(Open, Close) - Low) / ATR
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        atr = atr.replace(0, np.nan)
        
        max_oc = df[['open', 'close']].max(axis=1)
        min_oc = df[['open', 'close']].min(axis=1)
        
        upper_wick = (df['high'] - max_oc) / atr
        lower_wick = (min_oc - df['low']) / atr
        
        return pd.DataFrame({
            'upper_wick_ratio': upper_wick.fillna(0),
            'lower_wick_ratio': lower_wick.fillna(0)
        })
        
    @staticmethod
    def calculate_microstructure_stress(df: pd.DataFrame, period=20) -> pd.DataFrame:
        """
        Microstructure Stress
        - rolling volatility spike (Log returns rolling std z-score)
        - volume spike divergence
        """
        log_ret = np.log(df['close'] / df['close'].shift(1))
        vol = log_ret.rolling(period).std()
        
        vol_mean = vol.rolling(period).mean()
        vol_std = vol.rolling(period).std().replace(0, np.nan)
        vol_zscore = (vol - vol_mean) / vol_std
        
        if 'tick_volume' in df.columns:
            vol_mean_volume = df['tick_volume'].rolling(period).mean()
            vol_std_volume = df['tick_volume'].rolling(period).std().replace(0, np.nan)
            volume_zscore = (df['tick_volume'] - vol_mean_volume) / vol_std_volume
            
            # Divergence: High volume but low volatility, or high volatility but low volume
            # We can represent this simply as the difference in z-scores
            vol_div = volume_zscore - vol_zscore
        else:
            vol_div = pd.Series(0, index=df.index)
            
        return pd.DataFrame({
            'volatility_spike_z': vol_zscore.fillna(0),
            'volume_volatility_divergence': vol_div.fillna(0)
        })

    @classmethod
    def generate_all(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Appends all microstructure features to the dataframe
        """
        df_out = df.copy()
        df_out['cvd_proxy'] = cls.calculate_cvd_proxy(df)
        df_out['aggression_imbalance'] = cls.calculate_aggression_imbalance(df)
        
        wicks = cls.calculate_wick_pressure(df)
        df_out['upper_wick_ratio'] = wicks['upper_wick_ratio']
        df_out['lower_wick_ratio'] = wicks['lower_wick_ratio']
        
        stress = cls.calculate_microstructure_stress(df)
        df_out['volatility_spike_z'] = stress['volatility_spike_z']
        df_out['volume_volatility_divergence'] = stress['volume_volatility_divergence']
        
        return df_out
