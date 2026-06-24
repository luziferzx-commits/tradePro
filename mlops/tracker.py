import json
import os
import glob
from datetime import datetime

class ExperimentTracker:
    def __init__(self, base_dir="experiments"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    def _get_next_exp_id(self):
        existing = glob.glob(f"{self.base_dir}/exp_*")
        max_id = 0
        for f in existing:
            id_str = os.path.basename(f).replace("exp_", "")
            if id_str.isdigit():
                max_id = max(max_id, int(id_str))
        return max_id + 1
        
    def log_experiment(self, name, model_type, config, metrics, dataset_version):
        exp_id = self._get_next_exp_id()
        exp_name = f"exp_{exp_id:03d}"
        exp_dir = os.path.join(self.base_dir, exp_name)
        os.makedirs(exp_dir, exist_ok=True)
        
        data = {
            "experiment_id": exp_name,
            "name": name,
            "model_type": model_type,
            "timestamp": datetime.utcnow().isoformat(),
            "dataset_version": dataset_version,
            "config": config,
            "metrics": metrics
        }
        
        with open(os.path.join(exp_dir, "run.json"), "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"Logged experiment: {exp_name} ({name})")
        return exp_name

tracker = ExperimentTracker()
