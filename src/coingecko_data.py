"""
CoinGecko Data Collector for CryptoBot
Fetches trending coins, market data, and social metrics from CoinGecko API
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time


class CoinGeckoCollector:
    """Collects market and social data from CoinGecko API"""

    BASE_URL = "https://api.coingecko.com/api/v3"

    # Map Coinbase product IDs to CoinGecko IDs
    COIN_ID_MAP = {
        "BTC-USD": "bitcoin",
        "ETH-USD": "ethereum",
        "SOL-USD": "solana",
        "MATIC-USD": "matic-network",
        "AVAX-USD": "avalanche-2",
        "LINK-USD": "chainlink",
        "UNI-USD": "uniswap",
        "AAVE-USD": "aave",
        "ATOM-USD": "cosmos",
        "DOT-USD": "polkadot",
        "ADA-USD": "cardano",
        "XRP-USD": "ripple",
        "DOGE-USD": "dogecoin",
        "LTC-USD": "litecoin",
        "BCH-USD": "bitcoin-cash",
        "SHIB-USD": "shiba-inu",
        "ALGO-USD": "algorand",
        "XLM-USD": "stellar",
        "NEAR-USD": "near",
        "FIL-USD": "filecoin",
        "SAND-USD": "the-sandbox",
        "MANA-USD": "decentraland",
        "GRT-USD": "the-graph",
        "ICP-USD": "internet-computer",
        "APE-USD": "apecoin",
        "LDO-USD": "lido-dao",
        "ARB-USD": "arbitrum",
        "OP-USD": "optimism",
        "INJ-USD": "injective-protocol",
        "SUI-USD": "sui"
    }

    def __init__(self, config: Dict):
        """
        Initialize CoinGecko collector

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.CoinGecko")

        # Cache to avoid excessive API calls
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_minutes = config.get("coingecko_cache_minutes", 10)

        # Rate limiting - free tier: 10-50 calls/minute
        self.last_request_time = 0
        self.min_request_interval = 1.5  # 1.5 seconds between requests = ~40 calls/min

        # Trending cache (changes infrequently)
        self.trending_cache = None
        self.trending_cache_time = None
        self.trending_cache_minutes = 30  # Cache trending for 30 minutes

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

    def _get_coingecko_id(self, product_id: str) -> Optional[str]:
        """Get CoinGecko ID from product ID"""
        return self.COIN_ID_MAP.get(product_id)

    def get_trending_coins(self) -> Optional[List[Dict]]:
        """
        Get trending coins from CoinGecko

        Returns:
            List of trending coins with metadata or None
        """
        if not self.config.get("coingecko_enabled", False):
            return None

        # Check cache
        if self.trending_cache and self.trending_cache_time:
            age = datetime.now() - self.trending_cache_time
            if age.total_seconds() < (self.trending_cache_minutes * 60):
                return self.trending_cache

        try:
            self._rate_limit()

            endpoint = f"{self.BASE_URL}/search/trending"
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "coins" not in data:
                self.logger.warning("No trending coins in CoinGecko response")
                return None

            # Extract trending coin data
            trending_coins = []
            for item in data["coins"]:
                coin = item.get("item", {})
                trending_coins.append({
                    "id": coin.get("id"),
                    "symbol": coin.get("symbol", "").upper(),
                    "name": coin.get("name"),
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "score": coin.get("score", 0)
                })

            # Cache results
            self.trending_cache = trending_coins
            self.trending_cache_time = datetime.now()

            self.logger.info(f"Fetched {len(trending_coins)} trending coins from CoinGecko")
            return trending_coins

        except Exception as e:
            self.logger.error(f"Error fetching trending coins: {e}")
            return self.trending_cache  # Return old cache if available

    def get_coin_data(self, product_id: str) -> Optional[Dict]:
        """
        Get detailed coin data from CoinGecko

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            Dictionary with coin data or None
            {
                "social_score": 85,
                "developer_score": 78,
                "community_score": 92,
                "sentiment_votes_up_percentage": 68.5,
                "trending": True/False,
                "market_cap_rank": 1,
                "volume_24h": 25000000000,
                "price_change_24h_pct": 2.5
            }
        """
        if not self.config.get("coingecko_enabled", False):
            return None

        cache_key = f"coin_{product_id}"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        coingecko_id = self._get_coingecko_id(product_id)
        if not coingecko_id:
            self.logger.debug(f"No CoinGecko ID mapping for {product_id}")
            return None

        try:
            self._rate_limit()

            endpoint = f"{self.BASE_URL}/coins/{coingecko_id}"
            params = {
                "localization": "false",
                "tickers": "false",
                "community_data": "true",
                "developer_data": "true",
                "sparkline": "false"
            }

            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract relevant data
            coin_data = {
                "id": data.get("id"),
                "symbol": data.get("symbol", "").upper(),
                "market_cap_rank": data.get("market_cap_rank"),
                "trending": False,  # Will be updated by check_trending
                "sentiment_votes_up_percentage": data.get("sentiment_votes_up_percentage", 50),
                "social_score": 0,
                "community_score": 0,
                "developer_score": 0
            }

            # Community data
            community_data = data.get("community_data", {})
            if community_data:
                # Simple scoring based on social metrics
                twitter_followers = community_data.get("twitter_followers", 0)
                reddit_subscribers = community_data.get("reddit_subscribers", 0)

                # Normalize to 0-100 scale (rough estimates)
                twitter_score = min(twitter_followers / 10000, 100)  # 1M followers = 100
                reddit_score = min(reddit_subscribers / 5000, 100)   # 500k subs = 100

                coin_data["social_score"] = (twitter_score + reddit_score) / 2
                coin_data["community_score"] = coin_data["social_score"]

            # Developer data
            developer_data = data.get("developer_data", {})
            if developer_data:
                forks = developer_data.get("forks", 0)
                stars = developer_data.get("stars", 0)
                subscribers = developer_data.get("subscribers", 0)

                # Normalize to 0-100 scale
                dev_score = min((forks / 100 + stars / 100 + subscribers / 10) / 3, 100)
                coin_data["developer_score"] = dev_score

            # Market data
            market_data = data.get("market_data", {})
            if market_data:
                coin_data["price_change_24h_pct"] = market_data.get("price_change_percentage_24h", 0)
                coin_data["volume_24h"] = market_data.get("total_volume", {}).get("usd", 0)
                coin_data["market_cap"] = market_data.get("market_cap", {}).get("usd", 0)

            # Cache the result
            self._set_cache(cache_key, coin_data)

            return coin_data

        except Exception as e:
            self.logger.error(f"Error fetching coin data for {product_id}: {e}")
            return None

    def is_trending(self, product_id: str) -> bool:
        """
        Check if a coin is currently trending on CoinGecko

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            True if trending, False otherwise
        """
        symbol = self._extract_symbol(product_id)
        trending_coins = self.get_trending_coins()

        if not trending_coins:
            return False

        # Check if symbol is in trending list
        trending_symbols = [coin["symbol"] for coin in trending_coins]
        return symbol in trending_symbols

    def get_market_overview(self) -> Optional[Dict]:
        """
        Get global market overview from CoinGecko

        Returns:
            Dictionary with global market data
        """
        if not self.config.get("coingecko_enabled", False):
            return None

        cache_key = "market_overview"
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            self._rate_limit()

            endpoint = f"{self.BASE_URL}/global"
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()

            global_data = data.get("data", {})
            market_overview = {
                "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
                "total_volume_24h_usd": global_data.get("total_volume", {}).get("usd", 0),
                "btc_dominance": global_data.get("market_cap_percentage", {}).get("btc", 0),
                "eth_dominance": global_data.get("market_cap_percentage", {}).get("eth", 0),
                "market_cap_change_24h_pct": global_data.get("market_cap_change_percentage_24h_usd", 0),
                "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0)
            }

            self._set_cache(cache_key, market_overview)
            return market_overview

        except Exception as e:
            self.logger.error(f"Error fetching market overview: {e}")
            return None

    def should_boost_score(self, product_id: str) -> tuple[bool, float, str]:
        """
        Determine if a coin should get a score boost based on CoinGecko data

        Args:
            product_id: Product ID to check

        Returns:
            Tuple of (should_boost, boost_amount, reason)
        """
        coin_data = self.get_coin_data(product_id)
        if not coin_data:
            return False, 0, "No CoinGecko data available"

        boost = 0
        reasons = []

        # Check if trending
        if self.is_trending(product_id):
            boost += self.config.get("coingecko_trending_boost", 5)
            reasons.append("trending on CoinGecko")

        # Check sentiment
        sentiment = coin_data.get("sentiment_votes_up_percentage", 50)
        if sentiment > 70:
            boost += self.config.get("coingecko_sentiment_boost", 3)
            reasons.append(f"{sentiment:.0f}% positive sentiment")

        # Check social score
        social_score = coin_data.get("social_score", 0)
        if social_score > 50:
            boost += self.config.get("coingecko_social_boost", 2)
            reasons.append(f"high social activity ({social_score:.0f})")

        if boost > 0:
            reason = " + ".join(reasons)
            return True, boost, reason

        return False, 0, "No boost factors"

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.cache_timestamps.clear()
        self.trending_cache = None
        self.trending_cache_time = None
        self.logger.info("Cleared CoinGecko cache")
