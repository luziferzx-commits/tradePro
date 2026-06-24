from gqos.execution.pipeline import IPipelineStage, StageResult, PipelineContext
from gqos.messaging.contracts import MessageEnvelope
from gqos.sizing.events import SizePositionCommand
from gqos.risk.news_filter import NewsFilter

class NewsGuardStage(IPipelineStage):
    def __init__(self, news_filter: NewsFilter):
        self._news_filter = news_filter
        
    def process(self, envelope: MessageEnvelope, context: PipelineContext) -> StageResult:
        if not isinstance(envelope.payload, SizePositionCommand):
            return StageResult.continue_with(envelope)
            
        cmd = envelope.payload
        is_safe, reason = self._news_filter.is_safe_to_trade(symbol=cmd.symbol)
        
        if not is_safe:
            return StageResult.halt(f"Rejected by NewsGuard: {reason}", events=[])
            
        return StageResult.continue_with(envelope)
