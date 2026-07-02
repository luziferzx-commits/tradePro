import feedparser
import time
import logging

logger = logging.getLogger("MarketSentiment")

class MarketSentimentAnalyzer:
    _cache = {}
    _last_fetch = {}
    CACHE_TTL = 15 * 60  # 15 minutes
    
    # Generic Macro Keywords for traditional markets
    BULLISH_KEYWORDS = ["surge", "rally", "jump", "record", "growth", "boost", "optimism", "recovery", "soar", "gain"]
    BEARISH_KEYWORDS = ["crash", "plunge", "bear", "recession", "inflation", "hike", "fear", "drop", "slump", "loss", "warning"]
    
    FEEDS = {
        "FOREX": ["https://www.forexlive.com/feed/news"],
        "METALS": ["https://www.kitco.com/news/rss/kitco-news.rss"], # Or use forexlive as fallback
        "INDICES": ["https://feeds.a.dj.com/rss/RSSMarketsMain.xml"] # WSJ Markets
    }

    @classmethod
    def get_current_sentiment(cls, asset_class: str) -> dict:
        asset_class = asset_class.upper()
        now = time.time()
        
        # Check cache
        if asset_class in cls._cache and (now - cls._last_fetch.get(asset_class, 0)) < cls.CACHE_TTL:
            return cls._cache[asset_class]
            
        logger.info(f"Fetching fresh RSS feeds for {asset_class} sentiment analysis...")
        
        feeds_to_fetch = cls.FEEDS.get(asset_class, cls.FEEDS["FOREX"]) # fallback to forex
        headlines = []
        
        for feed_url in feeds_to_fetch:
            try:
                parsed = feedparser.parse(feed_url)
                for entry in parsed.entries[:20]:
                    title = getattr(entry, 'title', '')
                    summary = getattr(entry, 'summary', '')
                    headlines.append((title + " " + summary).lower())
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
                
        if not headlines:
            return {"sentiment": "NEUTRAL", "score": 0, "reason": "No news fetched"}
            
        bull_hits = 0
        bear_hits = 0
        
        for text in headlines:
            for word in cls.BULLISH_KEYWORDS:
                if word in text:
                    bull_hits += 1
            for word in cls.BEARISH_KEYWORDS:
                if word in text:
                    bear_hits += 1
                    
        net_score = (bull_hits - bear_hits) * 5
        net_score = max(min(net_score, 100), -100)
        
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
        
        cls._cache[asset_class] = result
        cls._last_fetch[asset_class] = now
        
        logger.info(f"{asset_class} Sentiment updated: {result['reason']}")
        return result
