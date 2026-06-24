import requests
import logging
from datetime import datetime, timedelta
import dateutil.parser

logger = logging.getLogger("GQOS.NewsFilter")

class NewsFilter:
    def __init__(self, block_minutes=15):
        self.block_minutes = block_minutes
        self.news_events = []
        self.last_fetch = None
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.monitored_currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"}

    def fetch_news(self):
        try:
            resp = requests.get(self.url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                events = []
                for item in data:
                    if item.get("impact") == "High" and item.get("country") in self.monitored_currencies:
                        try:
                            # The API returns time in US Eastern Time with offset e.g., "2026-06-21T21:00:00-04:00"
                            dt = dateutil.parser.isoparse(item["date"])
                            # Convert to naive UTC
                            dt_utc = dt.astimezone(dateutil.tz.UTC).replace(tzinfo=None)
                            events.append({
                                "title": item["title"],
                                "country": item["country"],
                                "time": dt_utc
                            })
                        except Exception as e:
                            logger.error(f"Error parsing date {item['date']}: {e}")
                self.news_events = events
                self.last_fetch = datetime.utcnow()
                logger.info(f"Fetched {len(self.news_events)} high-impact news events for this week.")
        except Exception as e:
            logger.error(f"Failed to fetch news from ForexFactory: {e}")

    def is_safe_to_trade(self, symbol=None):
        now = datetime.utcnow()
        # Refresh news if older than 12 hours
        if self.last_fetch is None or (now - self.last_fetch).total_seconds() > 12 * 3600:
            self.fetch_news()
            
        for event in self.news_events:
            # If symbol is provided, only block if the news currency is part of the symbol
            if symbol:
                if event["country"] not in symbol:
                    continue
                    
            time_diff = abs((now - event["time"]).total_seconds())
            if time_diff <= self.block_minutes * 60:
                logger.warning(f"NEWS BLOCK: {event['title']} ({event['country']}) is within {self.block_minutes} mins.")
                return False, f"News: {event['title']} ({event['country']})"
                
        return True, "Safe"
