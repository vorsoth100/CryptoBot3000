"""
LunarCrush Social Sentiment Client
Provides social media analytics and sentiment data for cryptocurrencies
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

try:
    from lunarcrush import LunarCrush
    LUNARCRUSH_AVAILABLE = True
except ImportError:
    LUNARCRUSH_AVAILABLE = False
    logging.warning("LunarCrush library not installed. Social sentiment features disabled.")


class LunarCrushClient:
    """Client for fetching social sentiment data from LunarCrush"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LunarCrush client

        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("CryptoBot.LunarCrush")
        self.config = config
        self.enabled = config.get("lunarcrush_enabled", True) and LUNARCRUSH_AVAILABLE

        if not LUNARCRUSH_AVAILABLE:
            self.logger.warning("LunarCrush library not available")
            self.enabled = False
            return

        try:
            # Initialize LunarCrush client (v2 - no API key needed)
            self.client = LunarCrush()
            self.cache = {}
            self.cache_expiry = {}
            self.cache_minutes = config.get("lunarcrush_cache_minutes", 30)

            self.logger.info("LunarCrush client initialized successfully")

        except Exception as e:
            self.logger.error(f"Error initializing LunarCrush client: {e}")
            self.enabled = False

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache or key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]

    def _set_cache(self, key: str, data: Any):
        """Cache data with expiry"""
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + timedelta(minutes=self.cache_minutes)

    def get_coin_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive social and market data for a coin

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Dictionary with social metrics or None if error
        """
        if not self.enabled:
            return None

        # Remove -USD suffix if present (LunarCrush uses just the symbol)
        symbol = symbol.replace('-USD', '')

        cache_key = f"coin_{symbol}"
        if self._is_cache_valid(cache_key):
            self.logger.debug(f"Using cached LunarCrush data for {symbol}")
            return self.cache[cache_key]

        try:
            # Get asset data from LunarCrush
            response = self.client.get_assets(symbol=symbol, data_points=1)

            if not response or 'data' not in response or not response['data']:
                self.logger.warning(f"No LunarCrush data found for {symbol}")
                return None

            coin_data = response['data'][0]

            # Extract key metrics
            metrics = {
                'symbol': coin_data.get('symbol'),
                'name': coin_data.get('name'),
                'galaxy_score': coin_data.get('galaxy_score'),
                'alt_rank': coin_data.get('alt_rank'),
                'social_volume': coin_data.get('social_volume_24h'),
                'social_score': coin_data.get('social_score'),
                'social_dominance': coin_data.get('social_dominance'),
                'sentiment': coin_data.get('average_sentiment'),
                'sentiment_absolute': coin_data.get('sentiment_absolute'),
                'sentiment_relative': coin_data.get('sentiment_relative'),
                'market_cap_rank': coin_data.get('market_cap_rank'),
                'percent_change_24h': coin_data.get('percent_change_24h'),
                'price': coin_data.get('price'),
                'volatility': coin_data.get('volatility'),
                'interactions_24h': coin_data.get('social_contributors'),
                'tweets_24h': coin_data.get('tweets'),
                'reddit_posts_24h': coin_data.get('reddit_posts'),
                'updated_at': coin_data.get('time')
            }

            self._set_cache(cache_key, metrics)
            self.logger.info(f"Fetched LunarCrush data for {symbol}: Galaxy Score={metrics.get('galaxy_score')}, "
                           f"Alt Rank={metrics.get('alt_rank')}, Sentiment={metrics.get('sentiment')}")

            return metrics

        except Exception as e:
            self.logger.error(f"Error fetching LunarCrush data for {symbol}: {e}")
            return None

    def get_market_overview(self) -> Optional[Dict[str, Any]]:
        """
        Get overall market sentiment and top trending coins

        Returns:
            Dictionary with market overview or None if error
        """
        if not self.enabled:
            return None

        cache_key = "market_overview"
        if self._is_cache_valid(cache_key):
            self.logger.debug("Using cached LunarCrush market overview")
            return self.cache[cache_key]

        try:
            # Get market data
            response = self.client.get_market(limit=10, sort='alt_rank')

            if not response or 'data' not in response:
                self.logger.warning("No LunarCrush market data found")
                return None

            market_data = response['data']

            # Calculate average sentiment across top coins
            total_sentiment = 0
            total_social_volume = 0
            coin_count = 0

            top_coins = []
            for coin in market_data[:10]:
                sentiment = coin.get('average_sentiment', 0)
                social_vol = coin.get('social_volume_24h', 0)

                if sentiment:
                    total_sentiment += sentiment
                    coin_count += 1

                total_social_volume += social_vol or 0

                top_coins.append({
                    'symbol': coin.get('symbol'),
                    'alt_rank': coin.get('alt_rank'),
                    'galaxy_score': coin.get('galaxy_score'),
                    'sentiment': sentiment
                })

            avg_sentiment = total_sentiment / coin_count if coin_count > 0 else 0

            overview = {
                'average_sentiment': avg_sentiment,
                'total_social_volume': total_social_volume,
                'top_trending': top_coins,
                'updated_at': datetime.now().isoformat()
            }

            self._set_cache(cache_key, overview)
            self.logger.info(f"Fetched LunarCrush market overview: Avg Sentiment={avg_sentiment:.2f}")

            return overview

        except Exception as e:
            self.logger.error(f"Error fetching LunarCrush market overview: {e}")
            return None

    def calculate_social_score(self, coin_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate a composite social score for trade analysis

        Args:
            coin_data: LunarCrush coin data

        Returns:
            Dictionary with scoring details
        """
        if not coin_data:
            return {
                'total_score': 0,
                'breakdown': {},
                'enabled': False
            }

        score = 0
        breakdown = {}

        # Galaxy Score contribution (0-100 scale)
        galaxy_score = coin_data.get('galaxy_score', 0) or 0
        galaxy_min = self.config.get('lunarcrush_galaxy_score_min', 50)

        if galaxy_score >= galaxy_min:
            galaxy_contribution = (galaxy_score - galaxy_min) / 2  # Max +25 points
            score += galaxy_contribution
            breakdown['galaxy_score'] = {
                'value': galaxy_score,
                'contribution': galaxy_contribution,
                'note': f'Above minimum threshold ({galaxy_min})'
            }
        else:
            breakdown['galaxy_score'] = {
                'value': galaxy_score,
                'contribution': 0,
                'note': f'Below minimum threshold ({galaxy_min})'
            }

        # AltRank contribution (lower is better)
        alt_rank = coin_data.get('alt_rank')
        if alt_rank and alt_rank <= 100:
            alt_boost = self.config.get('lunarcrush_alt_rank_boost', 4)
            alt_contribution = alt_boost * (100 - alt_rank) / 100  # Max configured boost
            score += alt_contribution
            breakdown['alt_rank'] = {
                'value': alt_rank,
                'contribution': alt_contribution,
                'note': f'Top 100 altcoin (rank {alt_rank})'
            }

        # Sentiment contribution
        sentiment = coin_data.get('sentiment', 0) or 0
        if sentiment > 0:
            sentiment_boost = self.config.get('lunarcrush_sentiment_boost', 3)
            # Sentiment is typically 0-5, normalize to 0-1
            sentiment_contribution = sentiment_boost * (sentiment / 5)
            score += sentiment_contribution
            breakdown['sentiment'] = {
                'value': sentiment,
                'contribution': sentiment_contribution,
                'note': 'Positive social sentiment'
            }

        # Social Volume contribution
        social_volume = coin_data.get('social_volume', 0) or 0
        if social_volume > 10000:  # Significant social activity
            volume_boost = self.config.get('lunarcrush_social_volume_boost', 5)
            # Log scale for social volume (very high numbers)
            import math
            volume_contribution = min(volume_boost, volume_boost * math.log10(social_volume / 10000))
            score += volume_contribution
            breakdown['social_volume'] = {
                'value': social_volume,
                'contribution': volume_contribution,
                'note': 'High social media activity'
            }

        return {
            'total_score': round(score, 2),
            'breakdown': breakdown,
            'enabled': True,
            'raw_data': {
                'galaxy_score': galaxy_score,
                'alt_rank': alt_rank,
                'sentiment': sentiment,
                'social_volume': social_volume
            }
        }

    def get_coin_summary(self, symbol: str) -> str:
        """
        Get a human-readable summary of coin's social metrics

        Args:
            symbol: Coin symbol

        Returns:
            Formatted string summary
        """
        data = self.get_coin_data(symbol)
        if not data:
            return f"No LunarCrush data available for {symbol}"

        summary = f"📱 LunarCrush Social Metrics for {symbol}:\n"
        summary += f"  • Galaxy Score: {data.get('galaxy_score', 'N/A')}/100\n"

        alt_rank = data.get('alt_rank')
        if alt_rank:
            summary += f"  • AltRank: #{alt_rank}\n"

        sentiment = data.get('sentiment')
        if sentiment:
            summary += f"  • Sentiment: {sentiment:.2f}/5 ({'Bullish' if sentiment > 3 else 'Bearish' if sentiment < 2.5 else 'Neutral'})\n"

        social_vol = data.get('social_volume')
        if social_vol:
            summary += f"  • Social Volume: {social_vol:,} mentions\n"

        return summary
