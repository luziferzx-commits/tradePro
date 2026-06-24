import hashlib
import json
from typing import Dict, Any, List, Type
import itertools
from dataclasses import asdict

from gqos.alpha.models import IAlphaModel, AlphaMetadata

class TemplateAlpha(IAlphaModel):
    """
    A concrete implementation of IAlphaModel that is constructed by the Factory.
    Stores its configuration parameters securely for reproducibility.
    """
    def __init__(self, template_name: str, parameters: Dict[str, Any], metadata: AlphaMetadata):
        self.template_name = template_name
        self.parameters = parameters
        self._metadata = metadata
        
        # Ensure deterministic hashing of the alpha_id
        param_str = json.dumps(parameters, sort_keys=True)
        hash_input = f"{template_name}_{param_str}".encode('utf-8')
        self._hash = hashlib.sha256(hash_input).hexdigest()
        self._alpha_id = f"alpha_{template_name}_{self._hash[:8]}"
        
    @property
    def alpha_id(self) -> str:
        return self._alpha_id
        
    @property
    def metadata(self) -> AlphaMetadata:
        # Clone metadata and inject parameter hash
        md_dict = asdict(self._metadata)
        md_dict["tags"] = md_dict.get("tags", []) + [f"hash:{self._hash}", f"template:{self.template_name}"]
        return AlphaMetadata(**md_dict)

    def required_features(self) -> List[str]:
        # Typically populated dynamically based on parameters (e.g. lookback windows)
        reqs = []
        for k, v in self.parameters.items():
            if isinstance(v, str) and v.startswith("feat_"):
                reqs.append(v)
        return reqs

    def generate_forecasts(self, dataset_hash: str, feature_manifest, features: Dict[str, Any]):
        raise NotImplementedError("TemplateAlpha expects vectorized execution or full event-driven engine")

class StrategyGenerator:
    """
    Generates deterministic Alpha candidate instances by taking a template and computing
    the Cartesian product of the parameter grid.
    """
    @staticmethod
    def generate_from_grid(template_name: str, param_grid: Dict[str, List[Any]], base_metadata: AlphaMetadata) -> List[TemplateAlpha]:
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        candidates = []
        for combination in itertools.product(*values):
            params = dict(zip(keys, combination))
            alpha = TemplateAlpha(template_name, params, base_metadata)
            candidates.append(alpha)
            
        return candidates
