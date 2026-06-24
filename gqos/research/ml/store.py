import os
import json
import hashlib
import pickle
from typing import Dict, Any, Optional

class MLModelArtifact:
    def __init__(self, model_obj: Any, model_hash: str, feature_hash: str, training_hash: str):
        self.model_obj = model_obj
        self.model_hash = model_hash
        self.feature_hash = feature_hash
        self.training_hash = training_hash

class ModelStore:
    def __init__(self, base_dir: str = ".gqos_models"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    def save(self, alpha_id: str, artifact: MLModelArtifact):
        model_dir = os.path.join(self.base_dir, alpha_id)
        os.makedirs(model_dir, exist_ok=True)
        
        # Save metadata
        metadata = {
            "model_hash": artifact.model_hash,
            "feature_hash": artifact.feature_hash,
            "training_hash": artifact.training_hash
        }
        with open(os.path.join(model_dir, "metadata.json"), 'w') as f:
            json.dump(metadata, f)
            
        # Save model object
        with open(os.path.join(model_dir, "model.pkl"), 'wb') as f:
            pickle.dump(artifact.model_obj, f)
            
    def load(self, alpha_id: str) -> Optional[MLModelArtifact]:
        model_dir = os.path.join(self.base_dir, alpha_id)
        if not os.path.exists(model_dir):
            return None
            
        with open(os.path.join(model_dir, "metadata.json"), 'r') as f:
            metadata = json.load(f)
            
        with open(os.path.join(model_dir, "model.pkl"), 'rb') as f:
            model_obj = pickle.load(f)
            
        return MLModelArtifact(
            model_obj=model_obj,
            model_hash=metadata["model_hash"],
            feature_hash=metadata["feature_hash"],
            training_hash=metadata["training_hash"]
        )
