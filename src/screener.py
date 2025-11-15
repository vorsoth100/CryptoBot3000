"""
Market Screener for CryptoBot
Scans coins for trading opportunities based on different strategies
"""

import logging
from typing import Dict, List, Optional
import pandas as pd
from src.signals import SignalGenerator


class MarketScreener:
    """Screens market for trading opportunities"""

    def __init__(self, config: Dict, data_collector, signal_generator: SignalGenerator):
        """
        Initialize market screener

        Args:
            config: Configuration dictionary
            data_collector: DataCollector instance
            signal_generator: SignalGenerator instance
        """
        self.config = config
        self.data_collector = data_collector
        self.signal_generator = signal_generator
        self.logger = logging.getLogger("CryptoBot.Screener")

    def screen_coins(self, mode: Optional[str] = None) -> List[Dict]:
        """
        Screen coins based on mode

        Args:
            mode: Screening mode (breakouts, oversold, support, trending)

        Returns:
            List of opportunities sorted by score
        """
        mode = mode or self.config.get("screener_mode", "breakouts")
        coins = self.config.get("screener_coins", [])

        self.logger.info(f"Screening {len(coins)} coins in '{mode}' mode")

        opportunities = []

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

                if score > 0:
                    opportunities.append({
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
                    })

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
