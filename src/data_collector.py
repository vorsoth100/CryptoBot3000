"""
Data Collector for CryptoBot
Fetches market data from Coinbase and CoinGecko APIs
Includes caching to minimize API calls
"""

import requests
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from src.utils import RateLimiter


class DataCollector:
    """Collects market data from various sources"""

    COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
    FEAR_GREED_URL = "https://api.alternative.me/fng/"

    # Mapping from Coinbase symbols to CoinGecko IDs
    COIN_ID_MAP = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "XRP": "ripple",
        "ADA": "cardano",
        "MATIC": "matic-network",
        "POL": "matic-network",  # POL is the new MATIC ticker
        "LINK": "chainlink",
        "DOT": "polkadot",
        "AVAX": "avalanche-2",
        "ATOM": "cosmos",
        "NEAR": "near",
        "APT": "aptos",
        "SUI": "sui",
        "UNI": "uniswap",
        "AAVE": "aave",
        "ARB": "arbitrum",
        "OP": "optimism",
        "RENDER": "render-token",
        "FET": "fetch-ai",
        "GRT": "the-graph",
        "PEPE": "pepe",
        "DOGE": "dogecoin",
        "LTC": "litecoin",
        "BCH": "bitcoin-cash",
        "ETC": "ethereum-classic",
        "TIA": "celestia",
        "INJ": "injective-protocol"
    }

    def __init__(self, coinbase_client, cache_minutes: int = 60):
        """
        Initialize data collector

        Args:
            coinbase_client: CoinbaseClient instance
            cache_minutes: Cache duration in minutes
        """
        self.coinbase = coinbase_client
        self.cache_minutes = cache_minutes
        self.logger = logging.getLogger("CryptoBot.DataCollector")

        # Rate limiters (reduced to 5 calls/min to avoid 429 errors)
        self.coingecko_limiter = RateLimiter(calls_per_minute=5)

        # Cache
        self.cache = {}
        self.cache_timestamps = {}

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache_timestamps:
            return False

        age = datetime.now() - self.cache_timestamps[key]
        return age.total_seconds() < (self.cache_minutes * 60)

    def _set_cache(self, key: str, data: Any):
        """Set cache with timestamp"""
        self.cache[key] = data
        self.cache_timestamps[key] = datetime.now()

    def get_current_price(self, product_id: str, use_cache: bool = True) -> Optional[float]:
        """
        Get current price from Coinbase

        Args:
            product_id: Product ID (e.g., BTC-USD)
            use_cache: Use cached price if available

        Returns:
            Current price
        """
        cache_key = f"price_{product_id}"

        if use_cache and self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        price = self.coinbase.get_current_price(product_id)

        if price:
            self._set_cache(cache_key, price)

        return price

    def get_historical_candles(self, product_id: str, granularity: str = "ONE_HOUR",
                              days: int = 30) -> Optional[pd.DataFrame]:
        """
        Get historical candles from Coinbase

        Args:
            product_id: Product ID (e.g., BTC-USD)
            granularity: Candle size
            days: Number of days of history

        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"candles_{product_id}_{granularity}_{days}"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        # Coinbase limits to 350 candles per request
        # Adjust days based on granularity to stay under limit
        max_candles = 350
        granularity_hours = {
            "ONE_MINUTE": 1/60,
            "FIVE_MINUTE": 5/60,
            "FIFTEEN_MINUTE": 15/60,
            "THIRTY_MINUTE": 30/60,
            "ONE_HOUR": 1,
            "TWO_HOUR": 2,
            "SIX_HOUR": 6,
            "ONE_DAY": 24
        }

        hours_per_candle = granularity_hours.get(granularity, 1)
        max_hours = max_candles * hours_per_candle
        max_days = max_hours / 24

        # Use the smaller of requested days or max allowed days
        actual_days = min(days, int(max_days))

        # Calculate start/end times as Unix timestamps
        end = datetime.utcnow()
        start = end - timedelta(days=actual_days)

        # Convert to Unix timestamps (seconds since epoch)
        start_unix = int(start.timestamp())
        end_unix = int(end.timestamp())

        candles = self.coinbase.get_candles(
            product_id,
            granularity,
            start=str(start_unix),
            end=str(end_unix)
        )

        if not candles:
            return None

        # Convert to DataFrame
        df = pd.DataFrame(candles)

        # Coinbase returns: start, low, high, open, close, volume
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['start'], unit='s')
            df = df.rename(columns={
                'low': 'low',
                'high': 'high',
                'open': 'open',
                'close': 'close',
                'volume': 'volume'
            })

            # Convert to numeric
            for col in ['low', 'high', 'open', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])

            df = df.sort_values('timestamp')
            df = df.set_index('timestamp')

            self._set_cache(cache_key, df)

        return df

    def get_market_data_coingecko(self, coin_symbol: str) -> Optional[Dict]:
        """
        Get market data from CoinGecko

        Args:
            coin_symbol: Coin symbol (e.g., BTC, ETH)

        Returns:
            Market data dictionary
        """
        cache_key = f"coingecko_{coin_symbol}"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        # Get CoinGecko ID
        coin_id = self.COIN_ID_MAP.get(coin_symbol)
        if not coin_id:
            self.logger.warning(f"No CoinGecko mapping for {coin_symbol}")
            return None

        try:
            self.coingecko_limiter.wait_if_needed()

            url = f"{self.COINGECKO_BASE_URL}/coins/{coin_id}"
            params = {
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Extract relevant data
            market_data = {
                "symbol": coin_symbol,
                "name": data.get("name"),
                "market_cap": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                "volume_24h": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                "price_change_24h": data.get("market_data", {}).get("price_change_percentage_24h"),
                "price_change_7d": data.get("market_data", {}).get("price_change_percentage_7d"),
                "price_change_30d": data.get("market_data", {}).get("price_change_percentage_30d"),
                "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
                "market_cap_rank": data.get("market_cap_rank")
            }

            self._set_cache(cache_key, market_data)
            return market_data

        except Exception as e:
            self.logger.error(f"Error fetching CoinGecko data for {coin_symbol}: {e}")
            return None

    def get_fear_greed_index(self) -> Optional[Dict]:
        """
        Get Fear & Greed Index from alternative.me

        Returns:
            Dictionary with fear/greed data
        """
        cache_key = "fear_greed"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            response = requests.get(self.FEAR_GREED_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                latest = data["data"][0]

                result = {
                    "value": int(latest["value"]),
                    "classification": latest["value_classification"],
                    "timestamp": datetime.fromtimestamp(int(latest["timestamp"]))
                }

                self._set_cache(cache_key, result)
                return result

        except Exception as e:
            self.logger.error(f"Error fetching Fear & Greed Index: {e}")

        return None

    def get_btc_dominance(self) -> Optional[float]:
        """
        Get Bitcoin dominance percentage

        Returns:
            BTC dominance as percentage
        """
        cache_key = "btc_dominance"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            self.coingecko_limiter.wait_if_needed()

            url = f"{self.COINGECKO_BASE_URL}/global"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data and "market_cap_percentage" in data["data"]:
                dominance = data["data"]["market_cap_percentage"].get("btc")

                if dominance:
                    self._set_cache(cache_key, dominance)
                    return dominance

        except Exception as e:
            self.logger.error(f"Error fetching BTC dominance: {e}")

        return None

    def get_top_coins_by_market_cap(self, limit: int = 50) -> Optional[List[Dict]]:
        """
        Get top cryptocurrencies by market cap from CoinGecko

        Args:
            limit: Number of coins to return

        Returns:
            List of coin dictionaries
        """
        cache_key = f"top_coins_{limit}"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            self.coingecko_limiter.wait_if_needed()

            url = f"{self.COINGECKO_BASE_URL}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            coins = []
            for coin in data:
                coins.append({
                    "symbol": coin["symbol"].upper(),
                    "name": coin["name"],
                    "market_cap": coin["market_cap"],
                    "volume_24h": coin["total_volume"],
                    "price": coin["current_price"],
                    "price_change_24h": coin["price_change_percentage_24h"],
                    "market_cap_rank": coin["market_cap_rank"]
                })

            self._set_cache(cache_key, coins)
            return coins

        except Exception as e:
            self.logger.error(f"Error fetching top coins: {e}")
            return None

    def get_coin_history(self, coin_symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Get historical price data from CoinGecko

        Args:
            coin_symbol: Coin symbol (e.g., BTC)
            days: Number of days of history

        Returns:
            DataFrame with price history
        """
        cache_key = f"history_{coin_symbol}_{days}"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        coin_id = self.COIN_ID_MAP.get(coin_symbol)
        if not coin_id:
            self.logger.warning(f"No CoinGecko mapping for {coin_symbol}")
            return None

        try:
            self.coingecko_limiter.wait_if_needed()

            url = f"{self.COINGECKO_BASE_URL}/coins/{coin_id}/market_chart"
            params = {
                "vs_currency": "usd",
                "days": days,
                "interval": "daily" if days > 1 else "hourly"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "prices" in data:
                df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")

                self._set_cache(cache_key, df)
                return df

        except Exception as e:
            self.logger.error(f"Error fetching coin history for {coin_symbol}: {e}")

        return None

    def get_multi_coin_data(self, coin_symbols: List[str]) -> Dict[str, Dict]:
        """
        Get market data for multiple coins

        Args:
            coin_symbols: List of coin symbols

        Returns:
            Dictionary mapping symbol to market data
        """
        results = {}

        for symbol in coin_symbols:
            data = self.get_market_data_coingecko(symbol)
            if data:
                results[symbol] = data

        return results

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.cache_timestamps.clear()
        self.logger.info("Cleared data cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "cached_items": len(self.cache),
            "oldest_cache": min(self.cache_timestamps.values()) if self.cache_timestamps else None,
            "newest_cache": max(self.cache_timestamps.values()) if self.cache_timestamps else None
        }
