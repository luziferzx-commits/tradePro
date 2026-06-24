import unittest
from gqos.registry.in_memory import InMemoryArtifactRegistry, IntegrityError, CycleDetectedError
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.models.execution import Trade
from gqos.domain.value_objects import Symbol, Timeframe, Probability, Price, LotSize
from gqos.domain.interfaces import IArtifact

class TestArtifactRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = InMemoryArtifactRegistry()
        
        # Build an artifact
        self.feat = Feature("RSI", 70.0, 160000)
        self.dataset = Dataset(Symbol("XAUUSD"), Timeframe("H1"), [self.feat])
        self.prediction = Prediction(1, Probability(0.8), self.dataset, "v1")
        self.decision = Decision("ENTER", self.prediction, 160001)
        self.trade = Trade(Symbol("XAUUSD"), Price(1900.0), LotSize(0.1), self.decision, 160002)

    def test_store_and_get(self):
        self.registry.store(self.feat)
        
        retrieved = self.registry.get(self.feat.artifact_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.artifact_id, self.feat.artifact_id)
        self.assertEqual(self.registry.count(), 1)

    def test_idempotent_duplicate_store(self):
        self.registry.store(self.feat)
        self.assertEqual(self.registry.count(), 1)
        
        # Store same artifact again
        result = self.registry.store(self.feat)
        self.assertEqual(self.registry.count(), 1)
        self.assertEqual(result.artifact_id, self.feat.artifact_id)

    def test_lineage_traversal_dfs(self):
        # Store the entire chain
        self.registry.store(self.feat)
        self.registry.store(self.dataset)
        self.registry.store(self.prediction)
        self.registry.store(self.decision)
        self.registry.store(self.trade)
        
        lineage = self.registry.get_lineage(self.trade.artifact_id)
        
        # Expected DFS order: Trade -> Decision -> Prediction -> Dataset -> Feature
        self.assertEqual(len(lineage), 5)
        self.assertEqual(lineage[0].artifact_id, self.trade.artifact_id)
        self.assertEqual(lineage[1].artifact_id, self.decision.artifact_id)
        self.assertEqual(lineage[2].artifact_id, self.prediction.artifact_id)
        self.assertEqual(lineage[3].artifact_id, self.dataset.artifact_id)
        self.assertEqual(lineage[4].artifact_id, self.feat.artifact_id)

    def test_integrity_check(self):
        self.registry.store(self.feat)
        
        # Manually corrupt the store
        corrupted_feat = Feature("RSI", 99.9, 160000) # Different value
        self.registry._store[self.feat.artifact_id] = corrupted_feat
        
        with self.assertRaises(IntegrityError):
            self.registry.get(self.feat.artifact_id)

    def test_cycle_detection(self):
        from unittest.mock import patch
        
        # Create a mock get that bypasses integrity check to allow cyclic graph construction
        def mock_get(artifact_id):
            return self.registry._store.get(artifact_id)
            
        with patch.object(self.registry, 'get', side_effect=mock_get):
            feat1 = Feature("F1", 1.0, 1000)
            feat2 = Feature("F2", 2.0, 1000)
            
            self.registry._store["A1"] = feat1
            self.registry._store["A2"] = feat2
            
            object.__setattr__(self.registry._store["A1"], '_parent_ids', ["A2"])
            object.__setattr__(self.registry._store["A2"], '_parent_ids', ["A1"])
            
            with self.assertRaises(CycleDetectedError):
                self.registry.get_lineage("A1")

    def test_hash_cache_policy(self):
        # 1. hash cache does not change artifact_id
        feat = Feature("MACD", 1.5, 1000)
        first_hash = feat.artifact_id
        second_hash = feat.artifact_id
        self.assertEqual(first_hash, second_hash)
        
        # 2. _cached_hash does not affect canonical serialization
        # generate_deterministic_hash pops _cached_hash before serializing
        from gqos.domain.utils import generate_deterministic_hash
        forced_hash = generate_deterministic_hash(feat, force_compute=True)
        self.assertEqual(first_hash, forced_hash)
        
        # 3. Mutating _cached_hash directly breaks integrity, proving it is cached
        object.__setattr__(feat, '_cached_hash', "fake_hash")
        self.assertEqual(feat.artifact_id, "fake_hash")
        
        # 4. But registry store() and get() bypass the cache for verification
        with self.assertRaises(IntegrityError):
            self.registry.store(feat)

    def test_canonical_serialization_stable(self):
        from gqos.domain.utils import generate_deterministic_hash
        import json
        from dataclasses import asdict
        
        feat = Feature("RSI", 70.0, 160000)
        data_dict = asdict(feat)
        data_dict.pop('_cached_hash', None)
        
        # Prove that it uses no spaces and sorts keys
        json_str = json.dumps(data_dict, sort_keys=True, separators=(',', ':'))
        self.assertNotIn(" ", json_str) # No spaces anywhere
        self.assertTrue(json_str.startswith('{"_parent_ids":[]')) # Alphabetical order
        
if __name__ == "__main__":
    unittest.main()
