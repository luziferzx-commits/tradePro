from typing import List, Dict, Set, Tuple
import pandas as pd
import hashlib

from gqos.alpha.exceptions import FeatureDependencyCycleError, MissingFeatureDependencyError
from gqos.alpha.features import IFeature, ICache
from gqos.alpha.manifest import FeatureManifest

class FeatureStore:
    def __init__(self, cache: ICache, features: List[IFeature]):
        self._cache = cache
        self._feature_map = {f.feature_id: f for f in features}
        
    def _build_lazy_dag(self, requested_features: List[str]) -> List[IFeature]:
        """
        Trims the DAG to only include requested_features and their ancestors.
        Performs a topological sort on this subgraph.
        """
        required = set()
        
        def _gather_dependencies(f_id: str, missing_origin: str):
            if f_id in required:
                return
            if f_id not in self._feature_map:
                raise MissingFeatureDependencyError(missing_origin, f_id)
            required.add(f_id)
            for dep in self._feature_map[f_id].dependencies():
                _gather_dependencies(dep, f_id)
                
        for r_id in requested_features:
            _gather_dependencies(r_id, "FeatureStore Request")

        # Now do Kahn's on the subgraph `required`
        adj: Dict[str, List[str]] = {f_id: [] for f_id in required}
        in_degree: Dict[str, int] = {f_id: 0 for f_id in required}
        
        for f_id in required:
            feature = self._feature_map[f_id]
            for dep in feature.dependencies():
                # Both dep and f_id are in required by definition of _gather_dependencies
                adj[dep].append(f_id)
                in_degree[f_id] += 1
                
        queue = [f_id for f_id in required if in_degree[f_id] == 0]
        sorted_ids = []
        
        while queue:
            node = queue.pop(0)
            sorted_ids.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        if len(sorted_ids) != len(required):
            cycle_nodes = [node for node in required if in_degree[node] > 0]
            raise FeatureDependencyCycleError(f"Cycle detected involving nodes: {cycle_nodes}")
            
        return [self._feature_map[f_id] for f_id in sorted_ids]

    def _generate_cache_key(self, dataset_hash: str, feature: IFeature) -> str:
        key_str = f"{dataset_hash}_{feature.feature_id}_{feature.metadata.calculate_hash()}"
        return hashlib.sha256(key_str.encode('utf-8')).hexdigest()

    def compute(self, dataset_hash: str, data: pd.DataFrame, requested_features: List[str]) -> Tuple[FeatureManifest, Dict[str, pd.Series]]:
        """
        Lazy computes ONLY the requested features and their dependencies in topological order.
        Returns a FeatureManifest tracking exactly what was executed, and the results dict.
        """
        sorted_features = self._build_lazy_dag(requested_features)
        results: Dict[str, pd.Series] = {}
        
        # Guard against mutation of the raw input
        safe_data = data.copy(deep=True)
        
        # For Manifest
        feature_hashes = []
        dependency_hashes = []
        cache_hashes = []
        execution_order = []
        
        for feature in sorted_features:
            cache_key = self._generate_cache_key(dataset_hash, feature)
            cached_series = self._cache.get(cache_key)
            
            execution_order.append(feature.feature_id)
            feature_hashes.append(feature.metadata.calculate_hash())
            dependency_hashes.extend(feature.dependencies())
            cache_hashes.append(cache_key)
            
            if cached_series is not None:
                results[feature.feature_id] = cached_series
            else:
                deps = {dep_id: results[dep_id] for dep_id in feature.dependencies()}
                computed = feature.compute(safe_data, deps)
                self._cache.set(cache_key, computed)
                results[feature.feature_id] = computed
                
        manifest_feature_hash = hashlib.sha256("".join(feature_hashes).encode('utf-8')).hexdigest()
        manifest_dependency_hash = hashlib.sha256("".join(dependency_hashes).encode('utf-8')).hexdigest()
        manifest_cache_hash = hashlib.sha256("".join(cache_hashes).encode('utf-8')).hexdigest()
        
        manifest = FeatureManifest(
            dataset_hash=dataset_hash,
            feature_hash=manifest_feature_hash,
            dependency_hash=manifest_dependency_hash,
            cache_hash=manifest_cache_hash,
            execution_order=execution_order,
            engine_version="1.0"
        )
                
        return manifest, results
