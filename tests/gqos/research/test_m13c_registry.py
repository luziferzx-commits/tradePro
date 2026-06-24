import os
import json
import tempfile


from gqos.research.experiment import ExperimentDefinition
from gqos.research.walk_forward.models import FoldManifest
from gqos.research.registry.models import StrategyCard, ExperimentResult, ResearchManifest
from gqos.research.registry.generator import StrategyCardGenerator
from gqos.research.registry.storage import ExperimentRegistry
from gqos.research.registry.exceptions import ExperimentAlreadyExistsError, ArtifactTamperedError

def get_dummy_data():
    definition = ExperimentDefinition(
        experiment_id="EXP-123",
        problem_hash="prob_hash",
        dataset_hash="ds_hash",
        strategy_hash="strat_hash",
        parameter_hash="param_hash",
        engine_version="1.0"
    )
    
    fm = FoldManifest(folds=[])
    result = ExperimentResult(
        definition=definition,
        fold_manifest=fm,
        evaluation_results=[]
    )
    
    card = StrategyCard(
        purpose="Momentum capture in crypto",
        markets=["BTC/USD", "ETH/USD"],
        timeframe="1h",
        factor_exposure={"Momentum": "High", "Value": "Low"},
        known_failure_modes=["Whipsaw markets"],
        walk_forward_metrics={"OOS Sharpe": "1.5"},
        risk_metrics={"Max Drawdown": "-10%"},
        data_version="v2",
        optimizer_version="v1",
        researcher="Quant A",
        approval_status="PENDING"
    )
    
    return definition, result, card

def test_strategy_card_generator():
    _, _, card = get_dummy_data()
    gen = StrategyCardGenerator()
    md = gen.generate_markdown(card)
    
    assert "# Strategy Card: Momentum capture in crypto" in md
    assert "- **Markets**: BTC/USD, ETH/USD" in md
    assert "- **OOS Sharpe**: 1.5" in md
    assert "- Whipsaw markets" in md

def test_registry_save_and_verify():
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = ExperimentRegistry(root_path=temp_dir)
        definition, result, card = get_dummy_data()
        
        manifest = registry.save_experiment("EXP-123", definition, result, card)
        
        # Verify bindings
        assert manifest.dataset_hash == "ds_hash"
        assert manifest.experiment_id == "EXP-123"
        assert manifest.result_hash == result.calculate_hash()
        assert manifest.card_hash == card.calculate_hash()
        
        # Verify files exist
        exp_path = os.path.join(temp_dir, "EXP-123")
        assert os.path.exists(os.path.join(exp_path, "manifest.json"))
        assert os.path.exists(os.path.join(exp_path, "strategy_card.md"))
        assert os.path.exists(os.path.join(exp_path, "artifact.sha256"))
        
        # Verify hashes via registry verification
        assert registry.verify_experiment("EXP-123") is True

def test_registry_no_overwrite():
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = ExperimentRegistry(root_path=temp_dir)
        definition, result, card = get_dummy_data()
        
        registry.save_experiment("EXP-123", definition, result, card)
        
        try:
            registry.save_experiment("EXP-123", definition, result, card)
            assert False, "Should raise ExperimentAlreadyExistsError"
        except ExperimentAlreadyExistsError:
            pass
            
        # Should work with overwrite=True
        registry.save_experiment("EXP-123", definition, result, card, overwrite=True)

def test_tamper_result_json():
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = ExperimentRegistry(root_path=temp_dir)
        definition, result, card = get_dummy_data()
        
        registry.save_experiment("EXP-123", definition, result, card)
        
        # Tamper result.json
        res_path = os.path.join(temp_dir, "EXP-123", "result.json")
        with open(res_path, 'w') as f:
            f.write('{"tampered": true}')
            
        try:
            registry.verify_experiment("EXP-123")
            assert False, "Should raise ArtifactTamperedError"
        except ArtifactTamperedError as e:
            assert "Artifact hash does not match" in str(e)

def test_tamper_strategy_card_markdown():
    with tempfile.TemporaryDirectory() as temp_dir:
        registry = ExperimentRegistry(root_path=temp_dir)
        definition, result, card = get_dummy_data()
        
        registry.save_experiment("EXP-123", definition, result, card)
        
        # Tamper strategy_card.md
        card_path = os.path.join(temp_dir, "EXP-123", "strategy_card.md")
        with open(card_path, 'a') as f:
            f.write('\n- **Sneaky addition**: 9.99 Sharpe')
            
        try:
            registry.verify_experiment("EXP-123")
            assert False, "Should raise ArtifactTamperedError"
        except ArtifactTamperedError as e:
            assert "Artifact hash does not match" in str(e)

if __name__ == "__main__":
    test_strategy_card_generator()
    test_registry_save_and_verify()
    test_registry_no_overwrite()
    test_tamper_result_json()
    test_tamper_strategy_card_markdown()
    print("M13C Experiment Registry tests passed!")
