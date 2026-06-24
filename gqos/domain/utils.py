import hashlib
import json
from dataclasses import asdict

def generate_deterministic_hash(dataclass_instance, force_compute=False) -> str:
    """
    Generates a deterministic SHA256 hash for a frozen dataclass.
    Recursively converts dataclasses and ValueObjects to primitives.
    Caches the hash to improve performance.
    """
    if not force_compute and hasattr(dataclass_instance, '_cached_hash'):
        return dataclass_instance._cached_hash
        
    def _default(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    # We convert to a dict, but we sort keys to ensure determinism
    # ValueObjects and nested dataclasses are handled by _default or asdict
    data_dict = asdict(dataclass_instance)
    data_dict.pop('_cached_hash', None)
    
    # Dump to JSON string with sorted keys, no spaces
    json_str = json.dumps(data_dict, sort_keys=True, separators=(',', ':'), default=_default)
    
    h = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    # Only cache if we didn't force compute, or if it wasn't cached yet
    if not force_compute or not hasattr(dataclass_instance, '_cached_hash'):
        object.__setattr__(dataclass_instance, '_cached_hash', h)
        
    return h
