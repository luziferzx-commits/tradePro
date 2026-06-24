from typing import List, Dict, Any, Union
import pandas as pd
import numpy as np

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult
from gqos.alpha.manifest import FeatureManifest

class IMetaMLModel:
    """
    Interface for the secondary Machine Learning model that predicts the probability of success.
    """
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        pass

class MetaLabeledAlpha(IAlphaModel):
    """
    Wrapper class that combines a primary directional Alpha with a secondary ML model.
    The primary Alpha provides the direction (-1, 0, 1).
    The ML model predicts the probability of the trade being profitable [0, 1].
    The Meta ML model cannot override the direction of the primary alpha.
    """
    def __init__(self, primary_alpha: IAlphaModel, meta_model: IMetaMLModel, ml_features: List[str]):
        self.primary_alpha = primary_alpha
        self.meta_model = meta_model
        self.ml_features = ml_features
        self._alpha_id = f"meta_{primary_alpha.alpha_id}"
        
    @property
    def alpha_id(self) -> str:
        return self._alpha_id
        
    @property
    def metadata(self) -> AlphaMetadata:
        return self.primary_alpha.metadata

    def required_features(self) -> List[str]:
        primary_req = self.primary_alpha.required_features()
        return list(set(primary_req + self.ml_features))

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        # Get base forecast from primary alpha
        primary_result = self.primary_alpha.generate_forecasts(dataset_hash, feature_manifest, features)
        df = primary_result.frame.copy()
        
        # Prepare features for ML model
        ml_input_df = pd.DataFrame({f: features[f] for f in self.ml_features})
        
        # Predict probability of success
        probabilities = self.meta_model.predict_proba(ml_input_df)
        
        # Enforce boundary: probability must be [0, 1]
        probabilities = np.clip(probabilities, 0.0, 1.0)
        
        # Meta model only adjusts confidence/sizing, never direction
        # Direction is determined by the sign of primary score
        direction = np.sign(df['score'])
        
        # The new score is the direction scaled by the ML probability
        df['score'] = direction * probabilities
        df['confidence'] = probabilities
        
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=df,
            explanations=primary_result.explanations
        )

class TripleBarrierMethod:
    @staticmethod
    def get_events(close: pd.Series, t_events: pd.DatetimeIndex, pt_sl: List[float], target: pd.Series, min_ret: float, num_threads: int = 1, t1: pd.Series = None) -> pd.DataFrame:
        """
        Advances the Triple Barrier Method.
        t_events: index of events (when a signal is generated)
        pt_sl: list of two floats [profit_taking_multiplier, stop_loss_multiplier].
               Set 0 to disable that barrier.
        target: Series of target volatility/returns (used to dynamically scale the barrier).
        t1: Series with vertical barrier timestamps.
        """
        # 1. Get target
        trgt = target.loc[t_events]
        trgt = trgt[trgt > min_ret]
        
        # 2. Get time of first touch
        if t1 is False:
            t1 = pd.Series(pd.NaT, index=t_events)
            
        # 3. Form events object
        # We will use a simplified path evaluation for the barriers
        out = pd.DataFrame(index=trgt.index)
        out['t1'] = t1.loc[trgt.index] if t1 is not None else pd.NaT
        out['trgt'] = trgt
        
        # Upper and lower barrier levels
        if pt_sl[0] > 0: out['pt'] = pt_sl[0] * trgt
        else: out['pt'] = pd.Series(index=trgt.index, dtype=float)
            
        if pt_sl[1] > 0: out['sl'] = -pt_sl[1] * trgt
        else: out['sl'] = pd.Series(index=trgt.index, dtype=float)
        
        # Path evaluation (simplified vectorized approximation)
        # Real implementation requires iterating through each path.
        first_touch_times = []
        hit_types = []
        returns_at_hit = []
        
        for loc, event in out.iterrows():
            start_price = close.loc[loc]
            end_time = event['t1']
            path = close.loc[loc : end_time] if pd.notna(end_time) else close.loc[loc :]
            
            # Remove start price observation
            if len(path) > 1: path = path.iloc[1:]
            
            path_returns = (path / start_price) - 1.0
            
            # Find hits
            pt_hit = path_returns[path_returns > event['pt']].index.min() if pd.notna(event['pt']) else pd.NaT
            sl_hit = path_returns[path_returns < event['sl']].index.min() if pd.notna(event['sl']) else pd.NaT
            
            # Determine which barrier hit first
            hits = {'pt': pt_hit, 'sl': sl_hit, 't1': end_time}
            valid_hits = {k: v for k, v in hits.items() if pd.notna(v)}
            
            if valid_hits:
                first_hit_type = min(valid_hits, key=valid_hits.get)
                first_hit_time = valid_hits[first_hit_type]
                first_touch_times.append(first_hit_time)
                hit_types.append(first_hit_type)
                
                # Get the return at hit exactly
                if first_hit_type == 'pt':
                    ret = path_returns.loc[first_hit_time]
                elif first_hit_type == 'sl':
                    ret = path_returns.loc[first_hit_time]
                else: # t1 vertical barrier
                    ret = path_returns.loc[first_hit_time] if first_hit_time in path_returns.index else path_returns.iloc[-1]
                    
                returns_at_hit.append(ret)
            else:
                # No hit (ran out of data)
                first_touch_times.append(pd.NaT)
                hit_types.append('none')
                returns_at_hit.append(np.nan)
                
        out['first_touch'] = first_touch_times
        out['hit_type'] = hit_types
        out['ret'] = returns_at_hit
        
        # Meta info
        out['holding_time'] = out['first_touch'] - out.index
        
        return out
