import feedparser
import time
import logging

logger = logging.getLogger("CryptoSentiment")

class CryptoSentimentAnalyzer:
    _cache = None
    _last_fetch = 0
    CACHE_TTL = 15 * 60  # 15 minutes in seconds
    
    # Simple Keyword Scoring
    BULLISH_KEYWORDS = ["surge", "rally", "jump", "adopt", "approval", "bull", "breakout", "ath", "pump", "record", "growth"]
    BEARISH_KEYWORDS = ["hack", "sec", "sue", "crash", "plunge", "bear", "ban", "delay", "scam", "fraud", "dump", "investigation"]
    
    FEEDS = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss"
    ]

    @classmethod
    def get_current_sentiment(cls) -> dict:
        """
        Fetches the latest crypto news via RSS and returns a sentiment score.
        Returns cached value if fetched within CACHE_TTL (15 mins).
        """
        now = time.time()
        if cls._cache and (now - cls._last_fetch) < cls.CACHE_TTL:
            return cls._cache
            
        logger.info("Fetching fresh Crypto News RSS feeds for sentiment analysis...")
        
        headlines = []
        for feed_url in cls.FEEDS:
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries[:20]: # Top 20 from each feed
                    headlines.append(entry.title.lower() + " " + entry.summary.lower())
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
                
        if not headlines:
            # Fallback if offline
            return {"sentiment": "NEUTRAL", "score": 0, "reason": "No news fetched"}
            
        bull_hits = 0
        bear_hits = 0
        
        # Analyze headlines
        for text in headlines:
            for word in cls.BULLISH_KEYWORDS:
                if word in text:
                    bull_hits += 1
            for word in cls.BEARISH_KEYWORDS:
                if word in text:
                    bear_hits += 1
                    
        # Calculate net score (-100 to +100 approx)
        # Assuming 40 headlines, if 10 have bear keywords, that's heavy bearish.
        net_score = (bull_hits - bear_hits) * 5
        net_score = max(min(net_score, 100), -100) # Clamp between -100 and +100
        
        if net_score >= 20:
            sentiment = "BULLISH"
        elif net_score <= -20:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
            
        result = {
            "sentiment": sentiment,
            "score": net_score,
            "bull_hits": bull_hits,
            "bear_hits": bear_hits,
            "reason": f"{sentiment} (Net: {net_score}, Bull: {bull_hits}, Bear: {bear_hits})"
        }
        
        cls._cache = result
        cls._last_fetch = now
        
        logger.info(f"Crypto Sentiment updated: {result['reason']}")
        return result
