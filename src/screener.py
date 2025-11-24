"""
Market Screener for CryptoBot
Scans coins for trading opportunities based on different strategies
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
from src.signals import SignalGenerator


class MarketScreener:
    """Screens market for trading opportunities"""

    def __init__(self, config: Dict, data_collector, signal_generator: SignalGenerator, news_sentiment=None, coingecko=None, claude_analyst=None, bot=None):
        """
        Initialize market screener

        Args:
            config: Configuration dictionary
            data_collector: DataCollector instance
            signal_generator: SignalGenerator instance
            news_sentiment: NewsSentiment instance (optional)
            coingecko: CoinGeckoCollector instance (optional)
            claude_analyst: ClaudeAnalyst instance (optional, for auto mode)
            bot: TradingBot instance (optional, to track mode selection)
        """
        self.config = config
        self.data_collector = data_collector
        self.signal_generator = signal_generator
        self.news_sentiment = news_sentiment
        self.coingecko = coingecko
        self.claude_analyst = claude_analyst
        self.bot = bot
        self.logger = logging.getLogger("CryptoBot.Screener")

    def screen_coins(self, mode: Optional[str] = None) -> List[Dict]:
        """
        Screen coins based on mode

        Args:
            mode: Screening mode (breakouts, oversold, support, trending, auto)

        Returns:
            List of opportunities sorted by score
        """
        mode = mode or self.config.get("screener_mode", "mean_reversion")

        # AUTO MODE: Let Claude AI decide best strategy
        if mode == "auto":
            if self.claude_analyst:
                # Collect market data for Claude
                market_data = {}
                try:
                    # Get BTC data as market benchmark
                    btc_changes = self.data_collector.get_price_changes("BTC-USD")
                    if btc_changes:
                        market_data['BTC-USD'] = btc_changes

                    # Get fear & greed if available
                    # This would need to be fetched from data_collector if implemented
                    market_data['fear_greed_index'] = {'value': 50}  # Default neutral

                    # Ask Claude for best mode
                    recommended_mode = self.claude_analyst.recommend_screener_mode(market_data)
                    self.logger.info(f"AUTO MODE: Claude recommends '{recommended_mode}' strategy")
                    mode = recommended_mode
                except Exception as e:
                    self.logger.error(f"Error in auto mode selection: {e}")
                    mode = "mean_reversion"  # Safe fallback
            else:
                self.logger.warning("AUTO mode selected but Claude not available, using mean_reversion")
                mode = "mean_reversion"

        # Track the selected mode in bot instance
        if self.bot:
            self.bot.current_screener_mode = mode
            self.bot.last_screener_mode_update = datetime.now()

        coins = self.config.get("screener_coins", [])

        self.logger.info(f"Screening {len(coins)} coins in '{mode}' mode")

        opportunities = []

        # Pre-fetch all news ONCE before looping to prevent multiple API calls
        if self.news_sentiment and self.config.get("news_sentiment_enabled", False):
            try:
                self.news_sentiment._fetch_all_news()
            except Exception as e:
                self.logger.warning(f"Failed to pre-fetch news data: {e}")

        # Pre-fetch trending coins ONCE before looping (single API call)
        if self.coingecko and self.config.get("coingecko_enabled", False):
            try:
                self.coingecko.get_trending_coins()
            except Exception as e:
                self.logger.warning(f"Failed to pre-fetch CoinGecko trending data: {e}")

        for product_id in coins:
            try:
                # Extract symbol (e.g., BTC from BTC-USD)
                symbol = product_id.split('-')[0]

                # Get price changes from Coinbase data
                price_changes = self.data_collector.get_price_changes(product_id) or {}

                # Get historical data for technical analysis
                df = self.data_collector.get_historical_candles(product_id, granularity="ONE_HOUR", days=30)
                if df is None or df.empty:
                    self.logger.debug(f"{product_id} skipped: no historical data")
                    continue

                # Calculate indicators
                df = self.signal_generator.generate_all_indicators(df)

                # Get signal
                signal_data = self.signal_generator.get_combined_signal(df)

                # Mode-specific scoring
                score = self._calculate_score(mode, df, signal_data, price_changes)

                # Get news sentiment if enabled
                news_data = None
                if self.news_sentiment and self.config.get("news_sentiment_enabled", False):
                    try:
                        news_data = self.news_sentiment.get_sentiment(product_id)

                        if news_data:
                            # Check if news sentiment blocks this opportunity
                            block_threshold = self.config.get("news_sentiment_block_threshold", -30)
                            if news_data["sentiment_score"] < block_threshold:
                                self.logger.warning(
                                    f"{product_id}: Blocked by negative news sentiment "
                                    f"({news_data['sentiment_score']}% < {block_threshold}%)"
                                )
                                if news_data["top_headlines"]:
                                    self.logger.warning(f"  Top headline: {news_data['top_headlines'][0][:100]}")
                                continue  # Skip this coin

                            # Boost score for positive news
                            boost_threshold = self.config.get("news_sentiment_boost_threshold", 50)
                            if news_data["sentiment_score"] > boost_threshold and news_data["trending"]:
                                score_boost = 10
                                score += score_boost
                                self.logger.info(
                                    f"{product_id}: Boosted score by +{score_boost} for positive news "
                                    f"({news_data['sentiment_score']}%)"
                                )

                    except Exception as e:
                        self.logger.error(f"Error fetching news sentiment for {product_id}: {e}")

                # Get CoinGecko trending boost (lightweight - no per-coin API calls)
                coingecko_data = None
                if self.coingecko and self.config.get("coingecko_enabled", False):
                    try:
                        # Only check if coin is trending (uses cached trending list, no individual API calls)
                        if self.coingecko.is_trending(product_id):
                            boost_amount = self.config.get("coingecko_trending_boost", 5)
                            score += boost_amount
                            self.logger.info(
                                f"{product_id}: Boosted score by +{boost_amount} for CoinGecko factors "
                                f"(trending on CoinGecko)"
                            )
                            coingecko_data = {"trending": True}
                    except Exception as e:
                        self.logger.error(f"Error checking CoinGecko trending for {product_id}: {e}")

                if score > 0:
                    opportunity = {
                        "product_id": product_id,
                        "symbol": symbol,
                        "score": score,
                        "signal": signal_data['signal'],
                        "confidence": signal_data['confidence'],
                        "price": df['close'].iloc[-1],
                        "volume_24h": price_changes.get("volume_24h"),
                        "price_change_24h": price_changes.get("price_change_24h"),
                        "price_change_7d": price_changes.get("price_change_7d"),
                        "price_change_30d": price_changes.get("price_change_30d"),
                        "indicators": signal_data['indicators'],
                        "volume_spike": signal_data['volume_spike']
                    }

                    # Add news sentiment data if available
                    if news_data:
                        opportunity["news_sentiment"] = news_data["sentiment_score"]
                        opportunity["news_trending"] = news_data["trending"]
                        opportunity["news_count"] = news_data["news_count"]

                    # Add CoinGecko data if available
                    if coingecko_data:
                        opportunity["coingecko_trending"] = self.coingecko.is_trending(product_id) if self.coingecko else False
                        opportunity["sentiment_votes_up_pct"] = coingecko_data.get("sentiment_votes_up_percentage", 50)
                        opportunity["social_score"] = coingecko_data.get("social_score", 0)
                        opportunity["market_cap_rank"] = coingecko_data.get("market_cap_rank")

                    opportunities.append(opportunity)

            except Exception as e:
                self.logger.error(f"Error screening {product_id}: {e}")
                continue

        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)

        # Limit results
        max_results = self.config.get("screener_max_results", 10)
        opportunities = opportunities[:max_results]

        self.logger.info(f"Found {len(opportunities)} opportunities")

        return opportunities

    def _calculate_score(self, mode: str, df: pd.DataFrame,
                        signal_data: Dict, market_data: Dict) -> float:
        """
        Calculate opportunity score based on mode

        Args:
            mode: Screening mode
            df: DataFrame with indicators
            signal_data: Signal data
            market_data: Market data from CoinGecko

        Returns:
            Score (0-100)
        """
        score = 0.0

        if mode == "breakouts":
            # High volume + momentum breakouts
            if self.signal_generator.detect_breakout(df):
                score += 40

            if signal_data['signal'] in ['buy', 'strong_buy']:
                score += 30

            if signal_data['volume_spike']:
                score += 20

            if market_data.get("price_change_24h", 0) > 5:
                score += 10

        elif mode == "oversold":
            # RSI oversold + volume spike
            rsi = signal_data['indicators'].get('rsi', 50)
            if rsi < 30:
                score += 40

            if signal_data['signal'] in ['buy', 'strong_buy']:
                score += 30

            if signal_data['volume_spike']:
                score += 20

            if market_data.get("price_change_24h", 0) < -5:
                score += 10

        elif mode == "support":
            # Price near support with bullish divergence
            if self.signal_generator.detect_support_bounce(df):
                score += 40

            if signal_data['signal'] in ['buy', 'strong_buy']:
                score += 30

            if signal_data['rsi_signal'] == 'buy':
                score += 20

            if signal_data['macd_signal'] == 'buy':
                score += 10

        elif mode == "trending":
            # Strong uptrend + above moving averages
            ma_short = signal_data['indicators'].get('ma_short', 0)
            ma_long = signal_data['indicators'].get('ma_long', 0)
            close = signal_data['indicators'].get('close', 0)

            if ma_short > ma_long and close > ma_short:
                score += 40

            if signal_data['signal'] in ['buy', 'strong_buy']:
                score += 30

            if market_data.get("price_change_7d", 0) > 10:
                score += 20

        elif mode == "momentum":
            # Hot coins: high volume + strong recent gains + momentum
            # Perfect for catching trending "hot" coins early

            # Volume spike is critical for momentum
            if signal_data['volume_spike']:
                score += 35

            # Strong buy signal
            if signal_data['signal'] == 'strong_buy':
                score += 30
            elif signal_data['signal'] == 'buy':
                score += 15

            # Recent price action (24h and 7d gains)
            price_change_24h = market_data.get("price_change_24h", 0)
            price_change_7d = market_data.get("price_change_7d", 0)

            if price_change_24h > 10:  # Up 10%+ today
                score += 25
            elif price_change_24h > 5:  # Up 5%+ today
                score += 15

            if price_change_7d > 20:  # Up 20%+ this week
                score += 10

            # RSI not overbought (room to run)
            rsi = signal_data['indicators'].get('rsi', 50)
            if rsi < 70:  # Not overbought yet
                score += 5

            if market_data.get("price_change_30d", 0) > 20:
                score += 10

        elif mode == "mean_reversion":
            # Bear market strategy: Buy extreme dips, sell bounces
            # Perfect for ranging/choppy markets
            reversion_data = self.signal_generator.detect_mean_reversion(df)

            if reversion_data['signal'] == 'buy':
                score += reversion_data['score']
            elif reversion_data['signal'] == 'sell':
                score += reversion_data['score']

            # Boost for volume confirmation
            if signal_data['volume_spike']:
                score += 15

        elif mode == "scalping":
            # Quick in/out trades (1-3% targets)
            # Perfect for volatile bear markets
            scalp_data = self.signal_generator.detect_scalping_opportunity(df)

            if scalp_data['signal'] == 'buy':
                score += scalp_data['score']
            elif scalp_data['signal'] == 'sell':
                score += scalp_data['score']

            # Volume is CRITICAL for scalping
            if scalp_data['volume_spike']:
                score += 25
            else:
                score *= 0.5  # Halve score without volume

        elif mode == "range_trading":
            # Buy support, sell resistance in consolidation
            # Perfect for sideways markets
            range_data = self.signal_generator.detect_range_trading(df)

            if range_data['in_range']:
                if range_data['signal'] == 'buy':
                    score += range_data['score']
                elif range_data['signal'] == 'sell':
                    score += range_data['score']

                # Boost for good position in range
                if range_data['signal'] == 'buy' and range_data['range_position'] < 0.15:
                    score += 20  # Very close to support
                elif range_data['signal'] == 'sell' and range_data['range_position'] > 0.85:
                    score += 20  # Very close to resistance

        elif mode == "bear_bounce":
            # Dead cat bounces in downtrends
            # High risk, tight stops required
            bounce_data = self.signal_generator.detect_dead_cat_bounce(df)

            if bounce_data['signal'] == 'buy':
                score += bounce_data['score']

                # Extra boost for extreme conditions
                if bounce_data['drop_pct'] < -20:  # 20%+ drop
                    score += 15

        # Apply confidence multiplier
        score = score * (signal_data['confidence'] / 100.0)

        return score

    def get_top_opportunity(self) -> Optional[Dict]:
        """
        Get single best opportunity

        Returns:
            Top opportunity or None
        """
        opportunities = self.screen_coins()

        if opportunities:
            return opportunities[0]

        return None
