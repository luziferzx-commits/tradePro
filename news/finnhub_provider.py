import logging
import requests
from typing import List, Dict
from datetime import datetime, timedelta
from news.provider import EconomicProvider
from config.settings import settings

logger = logging.getLogger(__name__)

class FinnhubProvider(EconomicProvider):
    def __init__(self):
        self.api_key = settings.FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1/calendar/economic"

    def get_events(self) -> List[Dict]:
        if not self.api_key:
            logger.warning("Finnhub API key not configured. Skipping news fetch.")
            return []
            
        try:
            # We look from now to next 24 hours
            now = datetime.utcnow()
            url = f"{self.base_url}?token={self.api_key}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = []
                for item in data.get('economicCalendar', []):
                    event_time = datetime.strptime(item['time'], "%Y-%m-%d %H:%M:%S")
                    if now <= event_time <= now + timedelta(hours=24):
                        # Filter for USD events if trading XAUUSD
                        if item.get('country') == 'US':
                            events.append({
                                'event': item.get('event'),
                                'impact': item.get('impact', 'low').upper(), # Finnhub returns 'low', 'medium', 'high'
                                'time': event_time
                            })
                return events
            else:
                logger.error(f"Finnhub API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching economic calendar: {e}")
            return []
