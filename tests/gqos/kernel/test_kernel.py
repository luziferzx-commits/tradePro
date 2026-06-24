import unittest
import threading
from gqos.kernel.interfaces import ILogger, IClock, IConfiguration
from gqos.kernel.di import Kernel, Lifetime
from gqos.kernel.implementations.SystemClock import SystemClock
from gqos.kernel.implementations.ConsoleLogger import ConsoleLogger
from gqos.kernel.implementations.EnvConfiguration import EnvConfiguration

class DummyService:
    pass

class TestKernel(unittest.TestCase):
    def setUp(self):
        Kernel.reset()
        self.kernel = Kernel.get_instance()

    def test_singleton_lifetime(self):
        self.kernel.register(DummyService, lambda: DummyService(), Lifetime.SINGLETON)
        
        instance1 = self.kernel.resolve(DummyService)
        instance2 = self.kernel.resolve(DummyService)
        
        self.assertIs(instance1, instance2, "Singleton should return the exact same instance")

    def test_transient_lifetime(self):
        self.kernel.register(DummyService, lambda: DummyService(), Lifetime.TRANSIENT)
        
        instance1 = self.kernel.resolve(DummyService)
        instance2 = self.kernel.resolve(DummyService)
        
        self.assertIsNot(instance1, instance2, "Transient should return a new instance every time")

    def test_unregistered_interface_raises_error(self):
        with self.assertRaises(ValueError):
            self.kernel.resolve(ILogger)

    def test_thread_safety_singleton_creation(self):
        self.kernel.register(DummyService, lambda: DummyService(), Lifetime.SINGLETON)
        instances = []
        
        def resolve_service():
            instances.append(self.kernel.resolve(DummyService))
            
        threads = [threading.Thread(target=resolve_service) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        self.assertEqual(len(instances), 100)
        # All instances should be identical
        first_instance = instances[0]
        for inst in instances:
            self.assertIs(inst, first_instance)

    def test_core_implementations_resolvable(self):
        self.kernel.register(IClock, lambda: SystemClock(), Lifetime.SINGLETON)
        self.kernel.register(ILogger, lambda: ConsoleLogger(), Lifetime.SINGLETON)
        self.kernel.register(IConfiguration, lambda: EnvConfiguration(), Lifetime.SINGLETON)
        
        clock = self.kernel.resolve(IClock)
        logger = self.kernel.resolve(ILogger)
        config = self.kernel.resolve(IConfiguration)
        
        self.assertTrue(hasattr(clock, 'now'))
        self.assertTrue(hasattr(logger, 'log'))
        self.assertTrue(hasattr(config, 'get'))

if __name__ == '__main__':
    unittest.main()
