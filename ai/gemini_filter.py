"""
DEPRECATED: GeminiFilter removed in V6.1.
Replaced by Quant+ML Consensus Engine.
This stub prevents ImportError in any legacy code that still references it.
"""
import logging

logger = logging.getLogger(__name__)


class GeminiFilter:
    """Deprecated no-op stub. Has zero effect on trade decisions."""

    def __init__(self):
        logger.warning(
            "GeminiFilter is DEPRECATED since V6.1 and has no effect. "
            "Remove all references to this class."
        )

    def filter(self, *args, **kwargs) -> bool:
        """Always pass-through (returns True)."""
        return True

    def analyze(self, *args, **kwargs) -> dict:
        return {"approved": True, "reason": "deprecated_stub", "confidence": 0.0}
