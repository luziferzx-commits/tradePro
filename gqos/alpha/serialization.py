import os
import json
import pandas as pd
from gqos.alpha.models import ForecastResult, ExplanationStore, IForecastSerializer

class ParquetForecastSerializer(IForecastSerializer):
    def serialize(self, result: ForecastResult, path: str):
        os.makedirs(path, exist_ok=True)
        
        # Save DataFrame as Parquet
        frame_path = os.path.join(path, "frame.parquet")
        result.frame.to_parquet(frame_path, engine="pyarrow", index=True)
        
        # Save Explanations as JSON
        exp_path = os.path.join(path, "explanations.json")
        with open(exp_path, 'w') as f:
            json.dump(result.explanations.store, f, indent=4)
            
        # Save Metadata as JSON
        meta_path = os.path.join(path, "meta.json")
        with open(meta_path, 'w') as f:
            json.dump({
                "alpha_id": result.alpha_id,
                "feature_manifest_hash": result.feature_manifest_hash
            }, f, indent=4)
            
    def deserialize(self, path: str) -> ForecastResult:
        frame_path = os.path.join(path, "frame.parquet")
        exp_path = os.path.join(path, "explanations.json")
        meta_path = os.path.join(path, "meta.json")
        
        frame = pd.read_parquet(frame_path, engine="pyarrow")
        
        with open(exp_path, 'r') as f:
            store_dict = json.load(f)
        explanations = ExplanationStore(store_dict)
        
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            
        return ForecastResult(
            alpha_id=meta["alpha_id"],
            feature_manifest_hash=meta["feature_manifest_hash"],
            frame=frame,
            explanations=explanations
        )
