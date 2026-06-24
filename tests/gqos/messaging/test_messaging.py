import unittest
import threading
import gc
from dataclasses import dataclass
from gqos.messaging.contracts import Event, Command, MessageEnvelope
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.kernel.implementations.ConsoleLogger import ConsoleLogger

@dataclass(frozen=True)
class TestEvent(Event):
    payload_data: str

@dataclass(frozen=True)
class AnotherEvent(Event):
    value: int

@dataclass(frozen=True)
class TestCommand(Command):
    instruction: str

class TestMessaging(unittest.TestCase):
    def setUp(self):
        self.logger = ConsoleLogger()
        self.event_bus = LocalEventBus(self.logger)
        self.cmd_bus = LocalCommandBus(self.logger)

    def test_publish_and_subscribe(self):
        received = []
        def handler(env: MessageEnvelope[TestEvent]):
            received.append(env.payload.payload_data)

        self.event_bus.subscribe(TestEvent, handler)
        
        env = MessageEnvelope.create(TestEvent("hello"), version=1)
        self.event_bus.publish(env)
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "hello")

    def test_unsubscribe(self):
        received = []
        def handler(env: MessageEnvelope[TestEvent]):
            received.append(env.payload.payload_data)

        self.event_bus.subscribe(TestEvent, handler)
        self.event_bus.unsubscribe(TestEvent, handler)
        
        env = MessageEnvelope.create(TestEvent("hello"), version=1)
        self.event_bus.publish(env)
        
        self.assertEqual(len(received), 0)

    def test_command_routing(self):
        def handler(env: MessageEnvelope[TestCommand]) -> str:
            return env.payload.instruction + "_executed"

        self.cmd_bus.register_handler(TestCommand, handler)
        
        env = MessageEnvelope.create(TestCommand("do_this"), version=1)
        result = self.cmd_bus.dispatch(env)
        
        self.assertEqual(result, "do_this_executed")

    def test_unknown_command(self):
        env = MessageEnvelope.create(TestCommand("do_this"), version=1)
        with self.assertRaises(ValueError):
            self.cmd_bus.dispatch(env)

    def test_multiple_command_handlers_raises_error(self):
        def handler1(env): pass
        def handler2(env): pass

        self.cmd_bus.register_handler(TestCommand, handler1)
        with self.assertRaises(ValueError):
            self.cmd_bus.register_handler(TestCommand, handler2)

    def test_subscriber_exception_policy(self):
        received = []
        
        def bad_handler(env):
            raise RuntimeError("Subscriber failed")
            
        def good_handler(env):
            received.append("ok")

        # Subscribe bad then good. Exception in bad should not stop good.
        self.event_bus.subscribe(TestEvent, bad_handler)
        self.event_bus.subscribe(TestEvent, good_handler)
        
        env = MessageEnvelope.create(TestEvent("hello"), version=1)
        
        # This should not raise
        self.event_bus.publish(env)
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "ok")

    def test_ordering_fifo(self):
        received = []
        def handler1(env): received.append(1)
        def handler2(env): received.append(2)
        def handler3(env): received.append(3)

        self.event_bus.subscribe(TestEvent, handler1)
        self.event_bus.subscribe(TestEvent, handler2)
        self.event_bus.subscribe(TestEvent, handler3)
        
        env = MessageEnvelope.create(TestEvent("hello"), version=1)
        self.event_bus.publish(env)
        
        self.assertEqual(received, [1, 2, 3])

    def test_nested_publish(self):
        received = []
        def inner_handler(env):
            received.append("inner")
            
        def outer_handler(env):
            received.append("outer")
            self.event_bus.publish(MessageEnvelope.create(AnotherEvent(42), version=1))

        self.event_bus.subscribe(TestEvent, outer_handler)
        self.event_bus.subscribe(AnotherEvent, inner_handler)
        
        self.event_bus.publish(MessageEnvelope.create(TestEvent("start"), version=1))
        
        self.assertEqual(received, ["outer", "inner"])

    def test_thread_safety(self):
        received = []
        lock = threading.Lock()
        
        def handler(env):
            with lock:
                received.append(1)

        self.event_bus.subscribe(TestEvent, handler)
        
        def worker():
            self.event_bus.publish(MessageEnvelope.create(TestEvent("x"), version=1))
            
        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        self.assertEqual(sum(received), 100)

    def test_memory_leak(self):
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        def handler(env): pass
        self.event_bus.subscribe(TestEvent, handler)
        
        for i in range(1000):
            env = MessageEnvelope.create(TestEvent("data"), version=1)
            self.event_bus.publish(env)
            
        gc.collect()
        final_objects = len(gc.get_objects())
        
        self.assertTrue((final_objects - initial_objects) < 500, "Potential memory leak in messaging.")

if __name__ == '__main__':
    unittest.main()
