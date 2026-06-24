from datetime import datetime
from gqos.kernel.interfaces import IClock

class SystemClock(IClock):
    """
    Implementation of IClock that uses standard system time (UTC).
    """
    def now(self) -> datetime:
        return datetime.utcnow()
