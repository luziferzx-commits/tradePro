import unittest
import threading
import sys
from gqos.registry.in_memory import InMemoryArtifactRegistry
from gqos.domain.models.data import Feature

class TestRegistryAdvanced(unittest.TestCase):
    def test_thread_safety(self):
        registry = InMemoryArtifactRegistry()
        features = [Feature(f"T{i}", i*1.0, 1000) for i in range(1000)]
        
        def worker(start, end):
            for i in range(start, end):
                registry.store(features[i])
                
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i*100, (i+1)*100))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        self.assertEqual(registry.count(), 1000)

    def test_memory_growth(self):
        registry = InMemoryArtifactRegistry()
        
        # 10k artifacts
        features = [Feature(f"M{i}", i*0.1, 1000) for i in range(10000)]
        for f in features:
            registry.store(f)
            
        store_size = sys.getsizeof(registry._store)
        print(f"\nMemory Size of 10k artifacts dictionary: {store_size / 1024:.2f} KB")
        self.assertEqual(registry.count(), 10000)

if __name__ == "__main__":
    unittest.main()
