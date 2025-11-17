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

        # Rate limiting - free tier is very limited
        self.last_request_time = 0
        self.min_request_interval = 3.0  # 3 seconds between requests for free tier

        # Batch cache for all news (free tier doesn't support per-coin filtering)
        self.all_news_cache = None
        self.all_news_cache_time = None

        # Failure tracking to prevent retry storms
        self.last_failure_time = None
        self.failure_count = 0
        self.backoff_minutes = 60  # Wait 60 minutes after failures (conservative for Crypto Panic free tier)

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

    def _fetch_all_news(self) -> Optional[List[Dict]]:
        """
        Fetch all crypto news (free tier doesn't support coin filtering)
        Uses aggressive caching to minimize API calls

        Returns:
            List of news items or None
        """
        # Check if cached news is still valid (30 min cache)
        if self.all_news_cache and self.all_news_cache_time:
            age = datetime.now() - self.all_news_cache_time
            if age.total_seconds() < (self.cache_minutes * 60):
                return self.all_news_cache

        # Check if we're in backoff period after failures
        if self.last_failure_time:
            time_since_failure = (datetime.now() - self.last_failure_time).total_seconds() / 60
            if time_since_failure < self.backoff_minutes:
                # Still in backoff period - return cached data or None
                self.logger.debug(
                    f"In backoff period ({time_since_failure:.1f}/{self.backoff_minutes} min) "
                    f"after {self.failure_count} failure(s). Skipping API call."
                )
                return self.all_news_cache  # May be None or old data

        try:
            # Rate limiting
            self._rate_limit()

            # Free tier: fetch general crypto news without coin filter
            params = {
                "auth_token": self.config.get("cryptopanic_api_key", "free"),
                "filter": "hot",  # Only hot/important news
                "public": "true"
            }

            self.logger.info("Fetching all crypto news from Crypto Panic...")
            response = requests.get(self.API_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "results" not in data:
                self.logger.warning("No results in Crypto Panic response")
                return None

            # Cache the results
            self.all_news_cache = data["results"]
            self.all_news_cache_time = datetime.now()

            # Reset failure tracking on success
            self.failure_count = 0
            self.last_failure_time = None

            self.logger.info(f"Cached {len(self.all_news_cache)} news items")
            return self.all_news_cache

        except requests.exceptions.HTTPError as e:
            # Track failures for backoff
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            # Check if it's a 429 rate limit error
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                self.logger.error(
                    f"Rate limit exceeded (429). Failure #{self.failure_count}. "
                    f"Waiting {self.backoff_minutes} min before retry. News sentiment disabled until then."
                )
            elif "429" in str(e):
                # Fallback check if response object isn't available but error message contains 429
                self.logger.error(
                    f"Rate limit exceeded (429). Failure #{self.failure_count}. "
                    f"Waiting {self.backoff_minutes} min before retry. News sentiment disabled until then."
                )
            else:
                self.logger.error(f"HTTP error fetching news: {e}")
            return self.all_news_cache  # Return old cache if available

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            self.logger.error(f"Error fetching news from Crypto Panic: {e}")
            return self.all_news_cache  # Return old cache if available

    def get_sentiment(self, product_id: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get news sentiment for a cryptocurrency

        Free tier optimization: Fetches all news once, filters locally by coin

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

            # Fetch all news (uses batch caching)
            all_news = self._fetch_all_news()

            if not all_news:
                return self._empty_sentiment()

            # Filter news for this specific coin locally
            coin_news = []
            lookback_hours = self.config.get("news_sentiment_lookback_hours", 24)
            cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

            for item in all_news:
                try:
                    # Check if this news mentions our coin
                    currencies = item.get("currencies", [])
                    if not currencies:
                        continue

                    # Check if coin is mentioned in currencies
                    coin_mentioned = False
                    for currency in currencies:
                        currency_code = currency.get("code", "").upper()
                        if currency_code == symbol.upper():
                            coin_mentioned = True
                            break

                    if not coin_mentioned:
                        continue

                    # Check time
                    published_at = datetime.strptime(item["published_at"], "%Y-%m-%dT%H:%M:%SZ")
                    if published_at >= cutoff_time:
                        coin_news.append(item)

                except Exception as e:
                    continue

            # Analyze sentiment from filtered news
            sentiment_data = self._analyze_news(coin_news, lookback_hours)

            # Add product_id for reference
            sentiment_data["product_id"] = product_id
            sentiment_data["symbol"] = symbol

            # Cache the result
            self._set_cache(cache_key, sentiment_data)

            return sentiment_data

        except Exception as e:
            self.logger.error(f"Error analyzing news sentiment for {product_id}: {e}")
            return self._empty_sentiment()

    def _analyze_news(self, news_items: List[Dict], lookback_hours: int) -> Dict:
        """
        Analyze news sentiment from Crypto Panic results

        Args:
            news_items: List of news items (already filtered by time)
            lookback_hours: How many hours to look back (not used, kept for compatibility)

        Returns:
            Sentiment analysis dictionary
        """
        # News is already filtered by caller
        recent_news = news_items

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
            # Use batch cache instead of making separate API call
            all_news = self._fetch_all_news()

            if not all_news:
                return "No recent market news available"

            news = all_news[:10]  # Top 10 stories

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
