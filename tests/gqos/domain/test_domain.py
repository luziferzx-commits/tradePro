import unittest
from gqos.domain.value_objects import Price, Probability, LotSize, Spread, Symbol, Timeframe
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.models.execution import Trade, Position
from gqos.domain.models.risk import RiskMetrics

class TestDomainModels(unittest.TestCase):

    def test_value_object_validation(self):
        # Valid cases
        p = Price(1900.5)
        self.assertEqual(p.value, 1900.5)

        prob = Probability(0.8)
        self.assertEqual(prob.value, 0.8)
        
        symbol = Symbol("xauusd")
        self.assertEqual(symbol.value, "XAUUSD") # Constructor should upper and strip

        # Invalid cases
        with self.assertRaises(ValueError):
            Price(-10)
        with self.assertRaises(ValueError):
            Price(0)
            
        with self.assertRaises(ValueError):
            Probability(1.5)
        with self.assertRaises(ValueError):
            Probability(-0.1)

        with self.assertRaises(ValueError):
            LotSize(0)
            
        with self.assertRaises(ValueError):
            Spread(-0.5)
            
        with self.assertRaises(ValueError):
            Symbol(" ")
            
        with self.assertRaises(ValueError):
            Timeframe("H3")

    def test_immutable_dataclasses(self):
        feat = Feature(name="RSI", value=70.5, timestamp=1600000)
        
        with self.assertRaises(Exception): # FrozenInstanceError
            feat.value = 80.0

    def test_deterministic_artifact_id(self):
        # Two identical objects should have the exact same artifact_id
        feat1 = Feature(name="MACD", value=1.5, timestamp=1600000)
        feat2 = Feature(name="MACD", value=1.5, timestamp=1600000)
        
        self.assertEqual(feat1.artifact_id, feat2.artifact_id)
        self.assertEqual(feat1, feat2) # __eq__ based on artifact_id
        
        # Changing one field should change the hash
        feat3 = Feature(name="MACD", value=1.6, timestamp=1600000)
        self.assertNotEqual(feat1.artifact_id, feat3.artifact_id)
        self.assertNotEqual(feat1, feat3)

    def test_composition_and_nested_hashing(self):
        # Build up to a Trade
        feat = Feature("EMA", 1900.0, 1600000)
        dataset = Dataset(Symbol("XAUUSD"), Timeframe("H1"), [feat])
        prediction = Prediction(1, Probability(0.85), dataset, "v1.0")
        decision = Decision("ENTER_LONG", prediction, 1600001)
        
        trade1 = Trade(
            symbol=Symbol("XAUUSD"),
            entry_price=Price(1905.0),
            lot_size=LotSize(0.1),
            decision=decision,
            timestamp=1600002
        )
        
        # Recreate identical graph
        feat_b = Feature("EMA", 1900.0, 1600000)
        dataset_b = Dataset(Symbol("XAUUSD"), Timeframe("H1"), [feat_b])
        prediction_b = Prediction(1, Probability(0.85), dataset_b, "v1.0")
        decision_b = Decision("ENTER_LONG", prediction_b, 1600001)
        
        trade2 = Trade(
            symbol=Symbol("XAUUSD"),
            entry_price=Price(1905.0),
            lot_size=LotSize(0.1),
            decision=decision_b,
            timestamp=1600002
        )

        self.assertEqual(trade1.artifact_id, trade2.artifact_id)
        
        # Test parent lineage
        self.assertIn(decision.artifact_id, trade1.parent_ids)
        self.assertIn(prediction.artifact_id, decision.parent_ids)
        self.assertIn(dataset.artifact_id, prediction.parent_ids)

    def test_risk_metrics_validation(self):
        # We need a Position
        feat = Feature("EMA", 1900.0, 1600000)
        dataset = Dataset(Symbol("XAUUSD"), Timeframe("H1"), [feat])
        prediction = Prediction(1, Probability(0.85), dataset, "v1.0")
        decision = Decision("ENTER_LONG", prediction, 1600001)
        trade = Trade(Symbol("XAUUSD"), Price(1905.0), LotSize(0.1), decision, 1600002)
        pos = Position(Symbol("XAUUSD"), LotSize(0.1), Price(1905.0), [trade])

        # Valid Risk
        risk = RiskMetrics(pos, 0.05, 100.0, 1600003)
        self.assertEqual(risk.drawdown_percent, 0.05)
        
        # Invalid Risk
        with self.assertRaises(ValueError):
            RiskMetrics(pos, -0.01, 100.0, 1600003)

if __name__ == '__main__':
    unittest.main()
