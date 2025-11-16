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

    FEAR_GREED_URL = "https://api.alternative.me/fng/"
    COINMARKETCAP_URL = "https://pro-api.coinmarketcap.com/v1"  # Requires API key (free tier: 10k calls/month)
    CRYPTOCOMPARE_URL = "https://min-api.cryptocompare.com/data"  # Free, 100k calls/month

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

    def get_price_changes(self, product_id: str) -> Optional[Dict]:
        """
        Calculate price changes from Coinbase historical data

        Args:
            product_id: Product ID (e.g., BTC-USD)

        Returns:
            Dictionary with 24h, 7d, 30d price changes
        """
        cache_key = f"price_changes_{product_id}"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            # Get current price
            current_price = self.get_current_price(product_id)
            if not current_price:
                return None

            # Get 30-day historical data
            df = self.get_historical_candles(product_id, granularity="ONE_DAY", days=30)
            if df is None or df.empty:
                return None

            # Calculate price changes
            changes = {}

            # 24h change (compare to 1 day ago)
            if len(df) >= 1:
                price_24h_ago = df['close'].iloc[-2] if len(df) >= 2 else df['close'].iloc[-1]
                changes['price_change_24h'] = ((current_price - price_24h_ago) / price_24h_ago) * 100

            # 7d change
            if len(df) >= 7:
                price_7d_ago = df['close'].iloc[-8] if len(df) >= 8 else df['close'].iloc[0]
                changes['price_change_7d'] = ((current_price - price_7d_ago) / price_7d_ago) * 100

            # 30d change
            if len(df) >= 30:
                price_30d_ago = df['close'].iloc[0]
                changes['price_change_30d'] = ((current_price - price_30d_ago) / price_30d_ago) * 100

            # 24h volume (sum of last 24 hourly candles)
            hourly_df = self.get_historical_candles(product_id, granularity="ONE_HOUR", days=1)
            if hourly_df is not None and not hourly_df.empty:
                changes['volume_24h'] = hourly_df['volume'].sum() * current_price  # Convert to USD

            self._set_cache(cache_key, changes)
            return changes

        except Exception as e:
            self.logger.error(f"Error calculating price changes for {product_id}: {e}")
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
        Get Bitcoin dominance percentage from CryptoCompare (free API)

        Returns:
            BTC dominance as percentage
        """
        cache_key = "btc_dominance"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            # CryptoCompare toplist endpoint (free, no key required)
            url = f"{self.CRYPTOCOMPARE_URL}/top/mktcapfull"
            params = {
                "limit": 100,  # Get top 100 coins
                "tsym": "USD"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "Data" in data:
                total_mktcap = 0
                btc_mktcap = 0

                for coin in data["Data"]:
                    coin_info = coin.get("CoinInfo", {})
                    raw_data = coin.get("RAW", {}).get("USD", {})

                    mktcap = raw_data.get("MKTCAP", 0)
                    total_mktcap += mktcap

                    if coin_info.get("Name") == "BTC":
                        btc_mktcap = mktcap

                if total_mktcap > 0 and btc_mktcap > 0:
                    dominance = (btc_mktcap / total_mktcap) * 100
                    self._set_cache(cache_key, dominance)
                    return dominance

        except Exception as e:
            self.logger.error(f"Error fetching BTC dominance from CryptoCompare: {e}")

        return None

    def get_market_snapshot(self) -> Optional[Dict]:
        """
        Get overall crypto market snapshot from CryptoCompare (free API)

        Returns:
            Dictionary with market overview data
        """
        cache_key = "market_snapshot"

        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]

        try:
            url = f"{self.CRYPTOCOMPARE_URL}/top/mktcapfull"
            params = {
                "limit": 10,  # Top 10 coins
                "tsym": "USD"
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "Data" in data:
                snapshot = {
                    "timestamp": datetime.now(),
                    "top_coins": []
                }

                for coin in data["Data"]:
                    coin_info = coin.get("CoinInfo", {})
                    raw_data = coin.get("RAW", {}).get("USD", {})

                    snapshot["top_coins"].append({
                        "symbol": coin_info.get("Name"),
                        "name": coin_info.get("FullName"),
                        "price": raw_data.get("PRICE"),
                        "market_cap": raw_data.get("MKTCAP"),
                        "volume_24h": raw_data.get("VOLUME24HOURTO"),
                        "change_24h": raw_data.get("CHANGEPCT24HOUR")
                    })

                self._set_cache(cache_key, snapshot)
                return snapshot

        except Exception as e:
            self.logger.error(f"Error fetching market snapshot: {e}")

        return None

    def get_historical_prices(self, product_id: str, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Get historical price data for charting

        Args:
            product_id: Product ID (e.g., BTC-USD)
            start_time: Start datetime
            end_time: End datetime

        Returns:
            List of {timestamp, price} dictionaries
        """
        try:
            # Calculate time range
            time_diff = end_time - start_time

            # Choose granularity based on time range
            if time_diff.days > 3:
                granularity = "ONE_HOUR"
            else:
                granularity = "FIFTEEN_MINUTE"

            # Get candles
            df = self.get_historical_candles(product_id, granularity=granularity, days=time_diff.days + 1)

            if df is None or df.empty:
                self.logger.warning(f"No historical data available for {product_id}")
                return []

            # Convert to list of {timestamp, price} for charting
            # Note: idx is the timestamp (set as index in get_historical_candles)
            price_history = []
            for idx, row in df.iterrows():
                price_history.append({
                    "timestamp": int(idx.timestamp() * 1000),  # idx is the timestamp
                    "price": float(row['close'])
                })

            return price_history

        except Exception as e:
            self.logger.error(f"Error getting historical prices for {product_id}: {e}")
            return []

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
