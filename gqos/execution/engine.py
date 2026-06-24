from typing import List
from gqos.execution.plugin import IPlugin
from gqos.messaging.interfaces import IEventBus, ICommandBus
from gqos.evidence.collector import EvidenceCollector
from gqos.evidence.events import ArtifactCreatedEvent
from gqos.execution.messages import TradeExecutedEvent

class ConfigurationError(Exception):
    pass

class ExecutionEngine:
    def __init__(self, command_bus: ICommandBus, event_bus: IEventBus, collector: EvidenceCollector):
        self.command_bus = command_bus
        self.event_bus = event_bus
        self.collector = collector
        self._plugins: List[IPlugin] = []

    def register_plugin(self, plugin: IPlugin):
        for cmd_type in plugin.supported_commands():
            try:
                # We define a closure so we can inject the event_bus into the plugin's handle method
                def create_handler(p=plugin):
                    return lambda env: p.handle(env, self.event_bus)
                
                self.command_bus.register_handler(cmd_type, create_handler())
            except ValueError as e:
                # Map bus duplicate handler error to ConfigurationError 
                # as demanded by exactly-one routing policy.
                raise ConfigurationError(f"Duplicate command handler: {str(e)}")
        
        self._plugins.append(plugin)
        
    def start(self):
        """Wires up the EvidenceCollector to listen to artifact-bearing events."""
        self.event_bus.subscribe(ArtifactCreatedEvent, self._handle_artifact_created)
        self.event_bus.subscribe(TradeExecutedEvent, self._handle_trade_executed)
        
    def _handle_artifact_created(self, envelope):
        self.collector.receive_artifact(envelope.payload.artifact)
        
    def _handle_trade_executed(self, envelope):
        # We extract the Trade artifact from the event and pass it to the collector
        self.collector.receive_artifact(envelope.payload.trade)
