"""
News Sentiment Analyzer for CryptoBot
Fetches and analyzes crypto news sentiment from Crypto Panic API
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time


class NewsSentiment:
    """Analyzes crypto news sentiment using Crypto Panic API"""

    API_URL = "https://cryptopanic.com/api/v1/posts/"

    def __init__(self, config: Dict):
        """
        Initialize news sentiment analyzer

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.NewsSentiment")

        # Cache to avoid excessive API calls
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_minutes = config.get("news_sentiment_cache_minutes", 30)

        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache_timestamps:
            return False

        age = datetime.now() - self.cache_timestamps[key]
        return age.total_seconds() < (self.cache_minutes * 60)

    def _set_cache(self, key: str, data: Dict):
        """Set cache with timestamp"""
        self.cache[key] = data
        self.cache_timestamps[key] = datetime.now()

    def _rate_limit(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _extract_symbol(self, product_id: str) -> str:
        """Extract coin symbol from product ID (e.g., BTC from BTC-USD)"""
        return product_id.split('-')[0]

    def get_sentiment(self, product_id: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get news sentiment for a cryptocurrency

        Args:
            product_id: Product ID (e.g., BTC-USD)
            use_cache: Use cached data if available

        Returns:
            Dictionary with sentiment data or None
            {
                "sentiment_score": 45,  # -100 (very bearish) to +100 (very bullish)
                "news_count": 23,
                "bullish_count": 15,
                "bearish_count": 8,
                "neutral_count": 0,
                "trending": False,
                "top_headlines": ["...", "..."],
                "recent_sentiment": "positive"  # positive, negative, neutral
            }
        """
        if not self.config.get("news_sentiment_enabled", False):
            return None

        cache_key = f"sentiment_{product_id}"

        if use_cache and self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            symbol = self._extract_symbol(product_id)

            # Rate limiting
            self._rate_limit()

            # Fetch news from Crypto Panic
            lookback_hours = self.config.get("news_sentiment_lookback_hours", 24)

            params = {
                "auth_token": self.config.get("cryptopanic_api_key", "free"),  # 'free' for public tier
                "currencies": symbol,
                "filter": "hot",  # Only hot/important news
                "public": "true"
            }

            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "results" not in data:
                self.logger.warning(f"No results in Crypto Panic response for {symbol}")
                return None

            # Analyze sentiment from news
            sentiment_data = self._analyze_news(data["results"], lookback_hours)

            # Add product_id for reference
            sentiment_data["product_id"] = product_id
            sentiment_data["symbol"] = symbol

            # Cache the result
            self._set_cache(cache_key, sentiment_data)

            return sentiment_data

        except Exception as e:
            self.logger.error(f"Error fetching news sentiment for {product_id}: {e}")
            return None

    def _analyze_news(self, news_items: List[Dict], lookback_hours: int) -> Dict:
        """
        Analyze news sentiment from Crypto Panic results

        Args:
            news_items: List of news items from API
            lookback_hours: How many hours to look back

        Returns:
            Sentiment analysis dictionary
        """
        # Filter news by time
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent_news = []

        for item in news_items:
            try:
                published_at = datetime.strptime(item["published_at"], "%Y-%m-%dT%H:%M:%SZ")
                if published_at >= cutoff_time:
                    recent_news.append(item)
            except:
                continue

        if not recent_news:
            return self._empty_sentiment()

        # Count sentiment votes
        bullish = 0
        bearish = 0
        important = 0
        saved = 0
        comments = 0

        headlines = []

        for item in recent_news:
            votes = item.get("votes", {})
            bullish += votes.get("positive", 0)
            bearish += votes.get("negative", 0)
            important += votes.get("important", 0)
            saved += votes.get("saved", 0)
            comments += votes.get("comments", 0)

            # Collect headlines (limit to top 5)
            if len(headlines) < 5:
                headlines.append(item.get("title", ""))

        total_votes = bullish + bearish
        news_count = len(recent_news)

        # Calculate sentiment score (-100 to +100)
        if total_votes > 0:
            # Weighted by vote count
            sentiment_score = ((bullish - bearish) / total_votes) * 100
        else:
            # No votes - use news volume as proxy
            # More news = more attention (slightly positive bias)
            sentiment_score = min(news_count * 2, 20) if news_count > 0 else 0

        # Determine if trending (high volume of news)
        trending = news_count >= 15 or important >= 5

        # Classify recent sentiment
        if sentiment_score > 30:
            recent_sentiment = "positive"
        elif sentiment_score < -30:
            recent_sentiment = "negative"
        else:
            recent_sentiment = "neutral"

        return {
            "sentiment_score": round(sentiment_score, 1),
            "news_count": news_count,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": total_votes - bullish - bearish if total_votes > 0 else 0,
            "important_count": important,
            "trending": trending,
            "top_headlines": headlines,
            "recent_sentiment": recent_sentiment,
            "engagement": saved + comments  # Total engagement metric
        }

    def _empty_sentiment(self) -> Dict:
        """Return empty sentiment data when no news available"""
        return {
            "sentiment_score": 0,
            "news_count": 0,
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "important_count": 0,
            "trending": False,
            "top_headlines": [],
            "recent_sentiment": "neutral",
            "engagement": 0
        }

    def get_batch_sentiment(self, product_ids: List[str]) -> Dict[str, Dict]:
        """
        Get sentiment for multiple coins at once

        Args:
            product_ids: List of product IDs

        Returns:
            Dictionary mapping product_id to sentiment data
        """
        results = {}

        for product_id in product_ids:
            sentiment = self.get_sentiment(product_id)
            if sentiment:
                results[product_id] = sentiment

        return results

    def should_block_trade(self, product_id: str) -> tuple[bool, str]:
        """
        Determine if a trade should be blocked based on news sentiment

        Args:
            product_id: Product ID to check

        Returns:
            Tuple of (should_block, reason)
        """
        sentiment = self.get_sentiment(product_id)

        if not sentiment:
            return False, "No news data available"

        threshold = self.config.get("news_sentiment_block_threshold", -30)

        if sentiment["sentiment_score"] < threshold:
            reason = f"Negative news sentiment ({sentiment['sentiment_score']}%) below threshold ({threshold}%)"

            if sentiment["top_headlines"]:
                reason += f" - Top headline: {sentiment['top_headlines'][0][:100]}"

            return True, reason

        return False, "News sentiment OK"

    def get_sentiment_summary(self) -> str:
        """Get a text summary of overall market news sentiment"""
        try:
            # Get overall crypto market news
            self._rate_limit()

            params = {
                "auth_token": self.config.get("cryptopanic_api_key", "free"),
                "filter": "hot",
                "public": "true"
            }

            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "results" not in data or not data["results"]:
                return "No recent market news available"

            news = data["results"][:10]  # Top 10 stories

            # Count sentiment
            bullish = sum(item.get("votes", {}).get("positive", 0) for item in news)
            bearish = sum(item.get("votes", {}).get("negative", 0) for item in news)

            total = bullish + bearish
            if total > 0:
                sentiment_pct = ((bullish - bearish) / total) * 100
            else:
                sentiment_pct = 0

            sentiment_label = "BULLISH" if sentiment_pct > 30 else "BEARISH" if sentiment_pct < -30 else "NEUTRAL"

            top_headlines = [item.get("title", "") for item in news[:3]]

            summary = f"Overall Market Sentiment: {sentiment_label} ({sentiment_pct:+.0f}%)\n"
            summary += f"Top Headlines:\n"
            for i, headline in enumerate(top_headlines, 1):
                summary += f"  {i}. {headline}\n"

            return summary

        except Exception as e:
            self.logger.error(f"Error getting sentiment summary: {e}")
            return "Error fetching market news sentiment"

    def clear_cache(self):
        """Clear all cached sentiment data"""
        self.cache.clear()
        self.cache_timestamps.clear()
        self.logger.info("Cleared news sentiment cache")
