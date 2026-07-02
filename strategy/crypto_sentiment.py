import requests
import logging
import time

logger = logging.getLogger(__name__)

class CryptoSentiment:
    _cached_value = None
    _cached_label = None
    _last_fetch = 0
    _CACHE_TTL = 3600  # 1 hour

    @classmethod
    def get_fear_greed_index(cls) -> dict:
        """
        Fetches the Fear and Greed index from alternative.me.
        Returns dict with 'value' (0-100) and 'label' (e.g. 'Extreme Fear').
        """
        now = time.time()
        if cls._cached_value is not None and (now - cls._last_fetch) < cls._CACHE_TTL:
            return {"value": cls._cached_value, "label": cls._cached_label}
            
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            r.raise_for_status()
            data = r.json()["data"][0]
            cls._cached_value = int(data["value"])
            cls._cached_label = data["value_classification"]
            cls._last_fetch = now
            logger.info(f"[CryptoSentiment] Updated Fear & Greed: {cls._cached_value} ({cls._cached_label})")
        except Exception as e:
            logger.warning(f"[CryptoSentiment] Failed to fetch Fear & Greed: {e}")
            if cls._cached_value is None:
                # Return neutral if failed and no cache
                return {"value": 50, "label": "Neutral"}
                
        return {"value": cls._cached_value, "label": cls._cached_label}
