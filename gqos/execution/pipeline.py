from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import IEventBus, ICommandBus
from gqos.sizing.portfolio import PortfolioSnapshot

@dataclass
class PipelineContext:
    snapshot: Optional[PortfolioSnapshot] = None
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StageResult:
    continue_pipeline: bool
    envelope: Optional[MessageEnvelope] = None
    reason: str = ""
    emitted_events: List[Event] = None
    
    @classmethod
    def continue_with(cls, envelope: MessageEnvelope) -> 'StageResult':
        return cls(continue_pipeline=True, envelope=envelope, emitted_events=[])
        
    @classmethod
    def halt(cls, reason: str, events: List[Event] = None) -> 'StageResult':
        return cls(continue_pipeline=False, envelope=None, reason=reason, emitted_events=events or [])

class IPipelineStage:
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        """
        Process the envelope. Can mutate or replace the envelope and return it via StageResult.
        """
        pass

class TradingPipeline:
    """
    A linear stage-based pipeline for processing trade decisions.
    Provides an alternative to the nested decorator command bus pattern.
    """
    def __init__(self, stages: List[IPipelineStage], event_bus: IEventBus):
        self._stages = stages
        self._event_bus = event_bus
        
    def dispatch(self, envelope: MessageEnvelope[Command]) -> Any:
        context = PipelineContext()
        current_envelope = envelope
        
        for stage in self._stages:
            result = stage.process(current_envelope, context)
            
            # Publish any events emitted by the stage
            if result.emitted_events:
                for event in result.emitted_events:
                    self._event_bus.publish(MessageEnvelope.create(
                        event,
                        version=current_envelope.version,
                        correlation_id=current_envelope.correlation_id
                    ))
            
            if not result.continue_pipeline:
                return f"Halted at {stage.__class__.__name__}: {result.reason}"
                
            current_envelope = result.envelope
            
        return "Completed pipeline execution."
