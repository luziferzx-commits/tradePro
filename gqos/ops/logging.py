import logging
import json
import traceback
from datetime import datetime
from typing import Any, Dict

class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the LogRecord.
    """
    def __init__(self, run_id: str = "default_run"):
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "component": record.name,
            "run_id": self.run_id,
            "message": record.getMessage(),
        }

        # Add explicit metadata if passed via extra kwarg
        if hasattr(record, "metadata"):
            log_obj["metadata"] = record.metadata
            
        # Add correlation tracing if passed
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        if hasattr(record, "trace_id"):
            log_obj["trace_id"] = record.trace_id

        # Exception details
        if record.exc_info:
            log_obj["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_obj)

def get_structured_logger(name: str, run_id: str = "default_run", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = JsonFormatter(run_id=run_id)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger
