import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler

class RegimeDiscovery:
    def __init__(self, n_regimes=3):
        self.n_regimes = n_regimes
        self.gmm = GaussianMixture(n_components=n_regimes, covariance_type='full', random_state=42)
        self.hmm_model = hmm.GaussianHMM(n_components=n_regimes, covariance_type='full', n_iter=100, random_state=42)
        self.scaler = StandardScaler()
        
    def _prepare_inputs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Volatility-first segmentation inputs
        - log returns rolling std
        - normalized ATR
        - volume z-score
        - session encoding (sine/cosine of hour)
        """
        df_feats = pd.DataFrame(index=df.index)
        
        # 1. Volatility: log returns rolling std
        log_ret = np.log(df['close'] / df['close'].shift(1))
        df_feats['vol_rolling_std'] = log_ret.rolling(20).std()
        
        # 2. Normalized ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        df_feats['norm_atr'] = atr / df['close']
        
        # 3. Volume Z-Score
        if 'tick_volume' in df.columns:
            vol_mean = df['tick_volume'].rolling(20).mean()
            vol_std = df['tick_volume'].rolling(20).std().replace(0, np.nan)
            df_feats['vol_zscore'] = (df['tick_volume'] - vol_mean) / vol_std
        else:
            df_feats['vol_zscore'] = 0.0
            
        # 4. Session Encoding
        # Assuming hour_utc or parse from index if it's a datetime
        if isinstance(df.index, pd.DatetimeIndex):
            hour = df.index.hour
        elif 'time' in df.columns:
            hour = pd.to_datetime(df['time']).dt.hour
        elif 'timestamp' in df.columns:
            hour = pd.to_datetime(df['timestamp']).dt.hour
        elif 'hour_utc' in df.columns:
            hour = df['hour_utc']
        else:
            hour = pd.Series(0, index=df.index)
            
        df_feats['session_sin'] = np.sin(2 * np.pi * hour / 24)
        df_feats['session_cos'] = np.cos(2 * np.pi * hour / 24)
        
        return df_feats.fillna(0)

    def fit_predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fits GMM + HMM Hybrid and returns the dataframe with regime labels.
        """
        X_df = self._prepare_inputs(df)
        
        # We need to drop initial zeros/nans for training, but keep shape for output
        # To simplify, we'll scale everything and let GMM/HMM handle it (they can handle dense arrays)
        X_scaled = self.scaler.fit_transform(X_df)
        
        # Layer 1: GMM (Probabilistic State)
        gmm_regimes = self.gmm.fit_predict(X_scaled)
        gmm_probs = self.gmm.predict_proba(X_scaled)
        
        # Layer 2: HMM (Temporal Stability)
        self.hmm_model.fit(X_scaled)
        hmm_regimes = self.hmm_model.predict(X_scaled)
        hmm_probs = self.hmm_model.predict_proba(X_scaled)
        
        df_out = df.copy()
        df_out['gmm_regime'] = gmm_regimes
        df_out['hmm_regime'] = hmm_regimes
        
        # Add probability confidences
        df_out['hmm_confidence'] = np.max(hmm_probs, axis=1)
        
        # Create a hybrid categorical regime if HMM is highly confident, else GMM
        df_out['hybrid_regime'] = np.where(df_out['hmm_confidence'] > 0.7, df_out['hmm_regime'], df_out['gmm_regime'])
        
        # Let's label the regimes meaningfully based on their volatility centers
        self._label_regimes(df_out, X_df)
        
        return df_out
        
    def _label_regimes(self, df_out: pd.DataFrame, X_df: pd.DataFrame):
        """
        Rename numeric regimes 0,1,2 into descriptive names based on their volatility signature.
        """
        # Map hmm_regime centers
        df_temp = pd.DataFrame({'regime': df_out['hmm_regime'], 'vol': X_df['vol_rolling_std']})
        means = df_temp.groupby('regime')['vol'].mean().sort_values()
        
        if len(means) == 3:
            mapping = {
                means.index[0]: 'LOW_VOL_COMPRESSION',
                means.index[1]: 'NORMAL_VOLATILITY',
                means.index[2]: 'HIGH_VOL_EXPANSION'
            }
        else:
            mapping = {i: f"REGIME_{i}" for i in means.index}
            
        df_out['regime_label'] = df_out['hybrid_regime'].map(mapping)
