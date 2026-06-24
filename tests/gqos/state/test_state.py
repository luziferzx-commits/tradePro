import unittest
import threading
import gc
from gqos.state.manager import StateManager
from gqos.state.models import StateSnapshot

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.manager = StateManager(initial_metadata={"RunID": "test-run"})

    def test_initial_snapshot_fidelity(self):
        snap = self.manager.get_snapshot()
        self.assertEqual(snap.version, 0)
        self.assertEqual(snap.metadata["RunID"], "test-run")
        self.assertEqual(snap.data, {})
        self.assertIsNone(snap.parent_version)

    def test_immutable_snapshot_cannot_be_mutated(self):
        self.manager.apply({"price": 1900.5})
        snap = self.manager.get_snapshot()
        
        # Test frozen dataclass exception
        with self.assertRaises(Exception): # FrozenInstanceError
            snap.version = 99
            
        # Test frozen dictionary exception (MappingProxyType does not support assignment)
        with self.assertRaises(TypeError):
            snap.data["price"] = 2000.0

    def test_monotonic_versioning_and_parenting(self):
        snap1 = self.manager.apply({"a": 1})
        self.assertEqual(snap1.version, 1)
        self.assertEqual(snap1.parent_version, 0)
        
        snap2 = self.manager.apply({"b": 2})
        self.assertEqual(snap2.version, 2)
        self.assertEqual(snap2.parent_version, 1)
        
        self.assertEqual(snap2.data["a"], 1)
        self.assertEqual(snap2.data["b"], 2)

    def test_snapshot_diff(self):
        snap0 = self.manager.get_snapshot()
        snap1 = self.manager.apply({"risk": 0.05, "spread": 1.2})
        snap2 = self.manager.apply({"risk": 0.06, "status": "active"})
        
        # Diff snap1 against snap0
        changes1 = snap1.diff(snap0)
        self.assertIn("risk", changes1)
        self.assertEqual(changes1["risk"], (0.05, None))
        
        # Diff snap2 against snap1
        changes2 = snap2.diff(snap1)
        self.assertIn("risk", changes2)
        self.assertEqual(changes2["risk"], (0.06, 0.05)) # (self, other)
        self.assertIn("status", changes2)
        self.assertEqual(changes2["status"], ("active", None))
        self.assertNotIn("spread", changes2) # Spread didn't change

    def test_deterministic_restore(self):
        snap1 = self.manager.apply({"state": "A"})
        snap2 = self.manager.apply({"state": "B"})
        
        self.assertEqual(self.manager.get_snapshot().data["state"], "B")
        self.assertEqual(self.manager.get_snapshot().version, 2)
        
        # Restore to snap1
        self.manager.restore(snap1)
        restored_snap = self.manager.get_snapshot()
        
        self.assertEqual(restored_snap.data["state"], "A")
        self.assertEqual(restored_snap.version, 1)
        
        # Mutate after restore
        snap3 = self.manager.apply({"state": "C"})
        self.assertEqual(snap3.version, 2) # It incremented from the restored version (1 -> 2)
        self.assertEqual(snap3.parent_version, 1)

    def test_thread_safety_concurrent_writes(self):
        """
        Verify that 100 threads applying changes simultaneously do not cause race conditions
        and the final version is exactly 100.
        """
        def worker(thread_id):
            self.manager.apply({f"key_{thread_id}": True})
            
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        final_snap = self.manager.get_snapshot()
        self.assertEqual(final_snap.version, 100)
        self.assertEqual(len(final_snap.data), 100)
        for i in range(100):
            self.assertTrue(final_snap.data[f"key_{i}"])

    def test_memory_leak_snapshots_are_garbage_collected(self):
        """
        If we don't hold references to old snapshots, they should be GC'd.
        """
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        for i in range(1000):
            self.manager.apply({"counter": i})
            
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # The number of objects shouldn't grow by thousands if snapshots are GC'd.
        # There might be slight variance due to Python internals, but it should be bounded.
        self.assertTrue((final_objects - initial_objects) < 500, "Potential memory leak: Old snapshots are not being garbage collected.")

if __name__ == '__main__':
    unittest.main()
