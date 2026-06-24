import os
import json
import hashlib
from typing import Dict, Any

from gqos.research.experiment import ExperimentDefinition
from gqos.research.registry.models import StrategyCard, ExperimentResult, ResearchManifest
from gqos.research.registry.generator import StrategyCardGenerator
from gqos.research.registry.exceptions import ExperimentAlreadyExistsError, ArtifactTamperedError

class ExperimentRegistry:
    def __init__(self, root_path: str = ".gqos/experiments"):
        self.root_path = root_path
        self.generator = StrategyCardGenerator()
        
    def _get_exp_path(self, experiment_id: str) -> str:
        return os.path.join(self.root_path, experiment_id)

    def _hash_file_content(self, filepath: str) -> str:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def save_experiment(
        self, 
        experiment_id: str, 
        definition: ExperimentDefinition, 
        result: ExperimentResult, 
        card: StrategyCard,
        overwrite: bool = False
    ) -> ResearchManifest:
        exp_path = self._get_exp_path(experiment_id)
        
        if os.path.exists(exp_path) and not overwrite:
            raise ExperimentAlreadyExistsError(experiment_id)
            
        os.makedirs(exp_path, exist_ok=True)
        
        # 1. Save Definition
        # For simplicity in this mock, we serialize just the dictionary representations.
        # In a real system, you'd use a robust serialization library like pydantic or marshmallow.
        def_path = os.path.join(exp_path, "definition.json")
        with open(def_path, 'w') as f:
            json.dump({
                "experiment_id": definition.experiment_id,
                "problem_hash": definition.problem_hash,
                "dataset_hash": definition.dataset_hash,
                "strategy_hash": definition.strategy_hash,
                "parameter_hash": definition.parameter_hash,
                "engine_version": definition.engine_version
            }, f, indent=4)
            
        # 2. Save Result (Mocked serialization for testing)
        res_path = os.path.join(exp_path, "result.json")
        with open(res_path, 'w') as f:
            json.dump({
                "definition_hash": result.definition.calculate_hash(),
                "fold_manifest_hash": result.fold_manifest.calculate_hash(),
                "evaluations_count": len(result.evaluation_results)
            }, f, indent=4)
            
        # 3. Generate & Save Strategy Card Markdown
        md_content = self.generator.generate_markdown(card)
        card_path = os.path.join(exp_path, "strategy_card.md")
        with open(card_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        # 4. Generate Manifest
        manifest = ResearchManifest(
            dataset_hash=definition.dataset_hash,
            experiment_id=experiment_id,
            result_hash=result.calculate_hash(),
            card_hash=card.calculate_hash()
        )
        
        man_path = os.path.join(exp_path, "manifest.json")
        with open(man_path, 'w') as f:
            json.dump({
                "dataset_hash": manifest.dataset_hash,
                "experiment_id": manifest.experiment_id,
                "result_hash": manifest.result_hash,
                "card_hash": manifest.card_hash
            }, f, indent=4)
            
        # 5. Compute global artifact hash combining all files
        # This guarantees detection of tampering for ANY file including Markdown
        hasher = hashlib.sha256()
        hasher.update(self._hash_file_content(def_path).encode('utf-8'))
        hasher.update(self._hash_file_content(res_path).encode('utf-8'))
        hasher.update(self._hash_file_content(card_path).encode('utf-8'))
        hasher.update(self._hash_file_content(man_path).encode('utf-8'))
        
        artifact_hash = hasher.hexdigest()
        
        art_path = os.path.join(exp_path, "artifact.sha256")
        with open(art_path, 'w') as f:
            f.write(artifact_hash)
            
        return manifest

    def verify_experiment(self, experiment_id: str) -> bool:
        exp_path = self._get_exp_path(experiment_id)
        
        def_path = os.path.join(exp_path, "definition.json")
        res_path = os.path.join(exp_path, "result.json")
        card_path = os.path.join(exp_path, "strategy_card.md")
        man_path = os.path.join(exp_path, "manifest.json")
        art_path = os.path.join(exp_path, "artifact.sha256")
        
        if not all(os.path.exists(p) for p in [def_path, res_path, card_path, man_path, art_path]):
            raise ArtifactTamperedError("Missing required files in experiment directory.")
            
        hasher = hashlib.sha256()
        hasher.update(self._hash_file_content(def_path).encode('utf-8'))
        hasher.update(self._hash_file_content(res_path).encode('utf-8'))
        hasher.update(self._hash_file_content(card_path).encode('utf-8'))
        hasher.update(self._hash_file_content(man_path).encode('utf-8'))
        
        computed_hash = hasher.hexdigest()
        
        with open(art_path, 'r') as f:
            expected_hash = f.read().strip()
            
        if computed_hash != expected_hash:
            raise ArtifactTamperedError("Artifact hash does not match computed hash from files.")
            
        return True
