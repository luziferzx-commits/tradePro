import os
import json
import shutil
import joblib
from datetime import datetime

class ModelRegistry:
    def __init__(self, base_dir="models"):
        self.base_dir = base_dir
        self.candidate_dir = os.path.join(base_dir, "candidate")
        self.validation_dir = os.path.join(base_dir, "validation")
        self.shadow_dir = os.path.join(base_dir, "shadow")
        self.production_dir = os.path.join(base_dir, "production")
        self.archive_dir = os.path.join(base_dir, "archive")
        
        for d in [self.candidate_dir, self.validation_dir, self.shadow_dir, self.production_dir, self.archive_dir]:
            os.makedirs(d, exist_ok=True)
            
    def promote_model(self, version, from_status, to_status):
        """
        Enforce flow: candidate -> validation -> shadow -> production
        """
        valid_transitions = {
            "candidate": ["validation", "archive"],
            "validation": ["shadow", "archive"],
            "shadow": ["production", "archive"],
            "production": ["archive"]
        }
        
        if to_status not in valid_transitions.get(from_status, []):
            raise ValueError(f"Invalid promotion from {from_status} to {to_status}")
            
        src_dir = os.path.join(getattr(self, f"{from_status}_dir"), version)
        dst_dir = os.path.join(getattr(self, f"{to_status}_dir"), version)
        
        if not os.path.exists(src_dir):
            raise FileNotFoundError(f"Model {version} not found in {from_status}")
            
        shutil.move(src_dir, dst_dir)
        print(f"Promoted model {version} from {from_status} to {to_status}")
        return True
        
    def get_symbol_dir(self, status, symbol=None):
        if symbol:
            target_dir = os.path.join(self.base_dir, symbol, status)
            os.makedirs(target_dir, exist_ok=True)
            return target_dir
        return getattr(self, f"{status}_dir")
        
    def register_model(self, model, metadata, status="candidate", symbol=None):
        version = metadata.get("model_version", f"v{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        metadata["model_version"] = version
        metadata["registered_at"] = datetime.utcnow().isoformat()
        
        target_dir = self.get_symbol_dir(status, symbol)
        model_dir = os.path.join(target_dir, version)
        os.makedirs(model_dir, exist_ok=True)
        
        joblib.dump(model, os.path.join(model_dir, "xgb.pkl"))
        with open(os.path.join(model_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)
            
        return version
        
    def get_production_model(self, symbol=None):
        prod_dir = os.path.join(self.base_dir, symbol, "production") if symbol else self.production_dir
        if not os.path.exists(prod_dir):
            return None, None
            
        models = os.listdir(prod_dir)
        if not models:
            return None, None
            
        latest_version = sorted(models)[-1]
        model_dir = os.path.join(prod_dir, latest_version)
        
        model_path = os.path.join(model_dir, "xgb.pkl")
        meta_path = os.path.join(model_dir, "metadata.json")
        
        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            return None, None
            
        model = joblib.load(model_path)
        with open(meta_path, "r") as f:
            metadata = json.load(f)
            
        return model, metadata

registry = ModelRegistry()
