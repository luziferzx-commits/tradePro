import logging
from datetime import datetime, timedelta
from news.finnhub_provider import FinnhubProvider

logger = logging.getLogger(__name__)

class EconomicFilter:
    def __init__(self, provider=None):
        self.provider = provider or FinnhubProvider()
        self.events_cache = []
        self.last_fetch = None
        self.fetch_interval = timedelta(hours=1)
        self.block_minutes_before = 30
        self.block_minutes_after = 30

    def refresh_events(self):
        now = datetime.utcnow()
        if not self.last_fetch or (now - self.last_fetch) > self.fetch_interval:
            self.events_cache = self.provider.get_events()
            self.last_fetch = now
            logger.info(f"Fetched {len(self.events_cache)} upcoming economic events.")

    def is_safe_to_trade(self) -> bool:
        """
        Returns False if we are within the block window of a HIGH impact event.
        """
        self.refresh_events()
        now = datetime.utcnow()
        
        for event in self.events_cache:
            if event['impact'] == 'HIGH':
                time_diff = event['time'] - now
                minutes_diff = time_diff.total_seconds() / 60.0
                
                # Check if we are within the window before or after
                if -self.block_minutes_after <= minutes_diff <= self.block_minutes_before:
                    logger.warning(f"Trading blocked due to high impact event: {event['event']} at {event['time']}")
                    return False
        return True
