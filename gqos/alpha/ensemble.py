from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import hashlib

from gqos.alpha.models import ForecastResult, ExplanationStore

class IEnsemble(ABC):
    @property
    @abstractmethod
    def ensemble_id(self) -> str:
        pass
        
    @abstractmethod
    def blend(self, forecasts: Dict[str, ForecastResult]) -> ForecastResult:
        """
        Blends multiple Alpha forecasts into a single unified forecast.
        `forecasts` maps alpha_id to ForecastResult.
        """
        pass

class StaticWeightEnsemble(IEnsemble):
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights
        
    @property
    def ensemble_id(self) -> str:
        return "StaticWeightEnsemble"
        
    def blend(self, forecasts: Dict[str, ForecastResult]) -> ForecastResult:
        # Validate that we have all required models
        for alpha_id in self.weights.keys():
            if alpha_id not in forecasts:
                raise ValueError(f"Ensemble missing required forecast for {alpha_id}")
                
        # Collect base DataFrames
        frames = []
        for alpha_id, result in forecasts.items():
            if alpha_id in self.weights:
                df = result.frame.copy()
                df["_weight"] = self.weights[alpha_id]
                df["_alpha_id"] = alpha_id
                frames.append(df)
                
        all_df = pd.concat(frames)
        
        # Calculate weighted score
        all_df["_weighted_score"] = all_df["score"] * all_df["_weight"]
        all_df["_abs_weight"] = all_df["_weight"].abs()
        all_df["_weighted_conf"] = all_df["confidence"] * all_df["_abs_weight"]
        
        grouped = all_df.groupby(level=0)
        
        # We need a unified feature manifest hash (concatenate and hash all underlying hashes)
        combined_manifests = "".join(sorted([res.feature_manifest_hash for res in forecasts.values()]))
        ensemble_manifest_hash = hashlib.sha256(combined_manifests.encode('utf-8')).hexdigest()
        
        blended_df = pd.DataFrame(index=grouped.groups.keys())
        blended_df["timestamp"] = blended_df.index
        blended_df["score"] = grouped["_weighted_score"].sum()
        
        sum_abs_weights = grouped["_abs_weight"].sum()
        # Prevent division by zero
        sum_abs_weights = sum_abs_weights.replace(0, np.nan)
        blended_df["confidence"] = grouped["_weighted_conf"].sum() / sum_abs_weights
        blended_df["confidence"] = blended_df["confidence"].fillna(0.0)
        
        blended_df["quality"] = grouped["quality"].min()
        
        # Take the shortest horizon and half-life as a conservative measure (simplified here to taking the first)
        blended_df["horizon"] = grouped["horizon"].first()
        blended_df["half_life"] = grouped["half_life"].first()
        
        # Generate new deterministic forecast_id
        blended_df["forecast_id"] = [
            hashlib.sha256(f"Ensemble_{self.ensemble_id}_{ensemble_manifest_hash}_{ts}".encode('utf-8')).hexdigest()
            for ts in blended_df["timestamp"]
        ]
        
        # Explanation Aggregation
        new_explanations = ExplanationStore({})
        
        # Group by timestamp again but iterate to build dicts
        # This can be slow in Python loops, but is necessary for deep hierarchical explanations
        for ts, group in grouped:
            f_id = blended_df.loc[ts, "forecast_id"]
            
            ts_exp = {}
            for _, row in group.iterrows():
                alpha_id = row["_alpha_id"]
                weight = row["_weight"]
                orig_f_id = row["forecast_id"]
                
                # Model-level explanation
                ts_exp[f"Model_{alpha_id}"] = row["score"] * weight
                
                # Feature-level explanation
                orig_exp = forecasts[alpha_id].explanations.get(orig_f_id)
                if orig_exp:
                    for feat_name, feat_val in orig_exp.items():
                        combined_key = f"Feature_{feat_name}"
                        ts_exp[combined_key] = ts_exp.get(combined_key, 0.0) + (feat_val * weight)
                        
            new_explanations.add(f_id, ts_exp)
            
        return ForecastResult(
            alpha_id=self.ensemble_id,
            feature_manifest_hash=ensemble_manifest_hash,
            frame=blended_df,
            explanations=new_explanations
        )
