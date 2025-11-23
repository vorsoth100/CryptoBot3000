"""
Technical Analysis Signals Module
Uses TA-Lib for indicator calculations
Generates buy/sell signals based on multiple indicators
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, List
import talib


class SignalGenerator:
    """Generates trading signals from technical indicators"""

    def __init__(self, config: Dict):
        """
        Initialize signal generator

        Args:
            config: Configuration dictionary with indicator settings
        """
        self.config = config
        self.logger = logging.getLogger("CryptoBot.Signals")

    def calculate_rsi(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index)

        Args:
            df: DataFrame with 'close' column
            period: RSI period (default from config)

        Returns:
            RSI series
        """
        period = period or self.config.get("rsi_period", 14)
        return talib.RSI(df['close'].values.astype(np.float64), timeperiod=period)

    def calculate_macd(self, df: pd.DataFrame) -> tuple:
        """
        Calculate MACD

        Args:
            df: DataFrame with 'close' column

        Returns:
            Tuple of (macd, signal, histogram)
        """
        fast = self.config.get("macd_fast", 12)
        slow = self.config.get("macd_slow", 26)
        signal = self.config.get("macd_signal", 9)

        macd, macd_signal, macd_hist = talib.MACD(
            df['close'].values.astype(np.float64),
            fastperiod=fast,
            slowperiod=slow,
            signalperiod=signal
        )

        return macd, macd_signal, macd_hist

    def calculate_bollinger_bands(self, df: pd.DataFrame) -> tuple:
        """
        Calculate Bollinger Bands

        Args:
            df: DataFrame with 'close' column

        Returns:
            Tuple of (upper, middle, lower)
        """
        period = self.config.get("bb_period", 20)
        std = self.config.get("bb_std", 2.0)

        upper, middle, lower = talib.BBANDS(
            df['close'].values.astype(np.float64),
            timeperiod=period,
            nbdevup=std,
            nbdevdn=std
        )

        return upper, middle, lower

    def calculate_moving_averages(self, df: pd.DataFrame) -> tuple:
        """
        Calculate moving averages

        Args:
            df: DataFrame with 'close' column

        Returns:
            Tuple of (ma_short, ma_long)
        """
        short_period = self.config.get("ma_short", 50)
        long_period = self.config.get("ma_long", 200)

        ma_short = talib.SMA(df['close'].values.astype(np.float64), timeperiod=short_period)
        ma_long = talib.SMA(df['close'].values.astype(np.float64), timeperiod=long_period)

        return ma_short, ma_long

    def calculate_volume_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Analyze volume patterns

        Args:
            df: DataFrame with 'volume' column

        Returns:
            Volume analysis dictionary
        """
        avg_volume = df['volume'].rolling(window=20).mean()
        current_volume = df['volume'].iloc[-1]
        volume_ratio = current_volume / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 0

        threshold = self.config.get("volume_spike_threshold", 2.0)

        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume.iloc[-1],
            "volume_ratio": volume_ratio,
            "is_spike": volume_ratio > threshold
        }

    def generate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all indicators and add to DataFrame

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with all indicators added
        """
        if df is None or df.empty:
            self.logger.error("Cannot calculate indicators on empty DataFrame")
            return df

        try:
            # RSI
            df['rsi'] = self.calculate_rsi(df)

            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(df)

            # Bollinger Bands
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.calculate_bollinger_bands(df)

            # Moving Averages
            df['ma_short'], df['ma_long'] = self.calculate_moving_averages(df)

            # Volume SMA
            df['volume_sma'] = talib.SMA(df['volume'].values.astype(np.float64), timeperiod=20)

            return df

        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            return df

    def get_rsi_signal(self, df: pd.DataFrame) -> str:
        """
        Get signal from RSI

        Args:
            df: DataFrame with RSI

        Returns:
            'buy', 'sell', or 'neutral'
        """
        if 'rsi' not in df.columns:
            return 'neutral'

        rsi = df['rsi'].iloc[-1]
        oversold = self.config.get("rsi_oversold", 30)
        overbought = self.config.get("rsi_overbought", 70)

        if rsi < oversold:
            return 'buy'
        elif rsi > overbought:
            return 'sell'
        else:
            return 'neutral'

    def get_macd_signal(self, df: pd.DataFrame) -> str:
        """
        Get signal from MACD

        Args:
            df: DataFrame with MACD

        Returns:
            'buy', 'sell', or 'neutral'
        """
        if 'macd' not in df.columns or 'macd_signal' not in df.columns:
            return 'neutral'

        macd = df['macd'].iloc[-1]
        macd_signal = df['macd_signal'].iloc[-1]
        macd_hist_prev = df['macd_hist'].iloc[-2] if len(df) > 1 else 0
        macd_hist = df['macd_hist'].iloc[-1]

        # Bullish crossover
        if macd > macd_signal and macd_hist_prev <= 0:
            return 'buy'
        # Bearish crossover
        elif macd < macd_signal and macd_hist_prev >= 0:
            return 'sell'
        else:
            return 'neutral'

    def get_bb_signal(self, df: pd.DataFrame) -> str:
        """
        Get signal from Bollinger Bands

        Args:
            df: DataFrame with Bollinger Bands

        Returns:
            'buy', 'sell', or 'neutral'
        """
        if 'bb_upper' not in df.columns or 'bb_lower' not in df.columns:
            return 'neutral'

        close = df['close'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]

        # Price touching lower band - potential buy
        if close <= bb_lower * 1.01:  # Within 1% of lower band
            return 'buy'
        # Price touching upper band - potential sell
        elif close >= bb_upper * 0.99:  # Within 1% of upper band
            return 'sell'
        else:
            return 'neutral'

    def get_ma_signal(self, df: pd.DataFrame) -> str:
        """
        Get signal from moving averages

        Args:
            df: DataFrame with moving averages

        Returns:
            'buy', 'sell', or 'neutral'
        """
        if 'ma_short' not in df.columns or 'ma_long' not in df.columns:
            return 'neutral'

        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        ma_short_prev = df['ma_short'].iloc[-2] if len(df) > 1 else 0
        ma_long_prev = df['ma_long'].iloc[-2] if len(df) > 1 else 0

        # Golden cross
        if ma_short > ma_long and ma_short_prev <= ma_long_prev:
            return 'buy'
        # Death cross
        elif ma_short < ma_long and ma_short_prev >= ma_long_prev:
            return 'sell'
        # Bullish trend (short MA above long MA)
        elif ma_short > ma_long:
            return 'buy'
        # Bearish trend
        elif ma_short < ma_long:
            return 'sell'
        else:
            return 'neutral'

    def get_combined_signal(self, df: pd.DataFrame) -> Dict:
        """
        Get combined signal from all indicators

        Args:
            df: DataFrame with all indicators

        Returns:
            Dictionary with signal details
        """
        # Get individual signals
        rsi_signal = self.get_rsi_signal(df)
        macd_signal = self.get_macd_signal(df)
        bb_signal = self.get_bb_signal(df)
        ma_signal = self.get_ma_signal(df)
        volume_analysis = self.calculate_volume_analysis(df)

        # Count votes
        buy_votes = sum([
            rsi_signal == 'buy',
            macd_signal == 'buy',
            bb_signal == 'buy',
            ma_signal == 'buy'
        ])

        sell_votes = sum([
            rsi_signal == 'sell',
            macd_signal == 'sell',
            bb_signal == 'sell',
            ma_signal == 'sell'
        ])

        # Determine overall signal
        if buy_votes >= 3:
            signal = 'strong_buy'
        elif buy_votes >= 2:
            signal = 'buy'
        elif sell_votes >= 3:
            signal = 'strong_sell'
        elif sell_votes >= 2:
            signal = 'sell'
        else:
            signal = 'neutral'

        # Calculate confidence (0-100)
        total_votes = max(buy_votes, sell_votes)
        confidence = (total_votes / 4.0) * 100

        # Boost confidence with volume spike
        if volume_analysis['is_spike']:
            confidence = min(100, confidence * 1.2)

        return {
            "signal": signal,
            "confidence": confidence,
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
            "rsi_signal": rsi_signal,
            "macd_signal": macd_signal,
            "bb_signal": bb_signal,
            "ma_signal": ma_signal,
            "volume_spike": volume_analysis['is_spike'],
            "volume_ratio": volume_analysis['volume_ratio'],
            "indicators": {
                "rsi": df['rsi'].iloc[-1] if 'rsi' in df.columns else None,
                "macd": df['macd'].iloc[-1] if 'macd' in df.columns else None,
                "macd_signal": df['macd_signal'].iloc[-1] if 'macd_signal' in df.columns else None,
                "close": df['close'].iloc[-1],
                "ma_short": df['ma_short'].iloc[-1] if 'ma_short' in df.columns else None,
                "ma_long": df['ma_long'].iloc[-1] if 'ma_long' in df.columns else None
            }
        }

    def detect_breakout(self, df: pd.DataFrame, periods: int = 20) -> bool:
        """
        Detect price breakout

        Args:
            df: DataFrame with price data
            periods: Lookback period

        Returns:
            True if breakout detected
        """
        if len(df) < periods + 1:
            return False

        current_close = df['close'].iloc[-1]
        high_period = df['high'].iloc[-periods:-1].max()

        # Price breaking above recent high with volume
        volume_analysis = self.calculate_volume_analysis(df)

        return (current_close > high_period and volume_analysis['is_spike'])

    def detect_support_bounce(self, df: pd.DataFrame, periods: int = 20) -> bool:
        """
        Detect bounce from support level

        Args:
            df: DataFrame with price data
            periods: Lookback period

        Returns:
            True if support bounce detected
        """
        if len(df) < periods + 1:
            return False

        current_close = df['close'].iloc[-1]
        low_period = df['low'].iloc[-periods:-1].min()

        # Price bouncing from support (within 2% of low)
        near_support = current_close <= low_period * 1.02

        # RSI oversold
        rsi_signal = self.get_rsi_signal(df)

        return (near_support and rsi_signal == 'buy')

    def detect_mean_reversion(self, df: pd.DataFrame) -> Dict:
        """
        Detect mean reversion opportunities (bear market strategy)

        Strategy: Buy extreme oversold dips, sell quick bounces
        Perfect for ranging/bear markets

        Args:
            df: DataFrame with indicators

        Returns:
            Dictionary with reversion signal and metrics
        """
        if len(df) < 50:
            return {"signal": "neutral", "score": 0}

        current_close = df['close'].iloc[-1]
        rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
        bb_lower = df['bb_lower'].iloc[-1] if 'bb_lower' in df.columns else current_close
        bb_middle = df['bb_middle'].iloc[-1] if 'bb_middle' in df.columns else current_close
        bb_upper = df['bb_upper'].iloc[-1] if 'bb_upper' in df.columns else current_close

        # Calculate distance from Bollinger bands
        bb_width = bb_upper - bb_lower
        distance_from_lower = (current_close - bb_lower) / bb_width if bb_width > 0 else 0.5
        distance_from_upper = (bb_upper - current_close) / bb_width if bb_width > 0 else 0.5

        score = 0
        signal = "neutral"

        # EXTREME OVERSOLD = BUY SIGNAL (mean reversion up)
        if rsi < 25 and distance_from_lower < 0.15:  # Very oversold + near lower BB
            signal = "buy"
            score = 80
        elif rsi < 30 and current_close < bb_lower:  # Oversold + below lower BB
            signal = "buy"
            score = 60
        elif rsi < 35 and distance_from_lower < 0.25:  # Mildly oversold + near lower BB
            signal = "buy"
            score = 40

        # OVERBOUGHT IN BEAR MARKET = SELL SIGNAL (fade the rally)
        elif rsi > 65 and distance_from_upper < 0.20:  # Overbought + near upper BB
            signal = "sell"
            score = 70
        elif rsi > 60 and current_close > bb_middle * 1.03:  # Above middle BB in bear market
            signal = "sell"
            score = 50

        return {
            "signal": signal,
            "score": score,
            "rsi": rsi,
            "bb_position": distance_from_lower  # 0 = at lower BB, 1 = at upper BB
        }

    def detect_scalping_opportunity(self, df: pd.DataFrame) -> Dict:
        """
        Detect quick scalping opportunities (1-3% moves)

        Strategy: High volume + momentum shifts for quick in/out
        Perfect for volatile bear markets

        Args:
            df: DataFrame with indicators

        Returns:
            Dictionary with scalping signal and metrics
        """
        if len(df) < 20:
            return {"signal": "neutral", "score": 0}

        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
        macd_hist = df['macd_hist'].iloc[-1] if 'macd_hist' in df.columns else 0
        macd_hist_prev = df['macd_hist'].iloc[-2] if 'macd_hist' in df.columns else 0

        # Volume spike detection
        volume_analysis = self.calculate_volume_analysis(df)
        volume_spike = volume_analysis['is_spike']

        # Price momentum (short-term)
        price_change_1h = (current_close - prev_close) / prev_close
        price_change_3h = (current_close - df['close'].iloc[-4]) / df['close'].iloc[-4] if len(df) >= 4 else 0

        # MACD histogram momentum shift
        macd_turning_up = macd_hist > macd_hist_prev and macd_hist_prev < 0
        macd_turning_down = macd_hist < macd_hist_prev and macd_hist_prev > 0

        score = 0
        signal = "neutral"

        # BUY SCALP: Momentum shift + volume
        if volume_spike and macd_turning_up and rsi < 50:
            score = 70
            signal = "buy"
        elif price_change_1h > 0.01 and volume_spike and rsi < 55:  # 1%+ move with volume
            score = 60
            signal = "buy"
        elif macd_turning_up and rsi < 45:
            score = 40
            signal = "buy"

        # SELL SCALP: Quick profit taking
        elif price_change_3h > 0.025 and rsi > 60:  # 2.5%+ profit + overbought
            score = 65
            signal = "sell"
        elif macd_turning_down and rsi > 55:
            score = 50
            signal = "sell"

        return {
            "signal": signal,
            "score": score,
            "volume_spike": volume_spike,
            "momentum_1h": price_change_1h * 100,
            "momentum_3h": price_change_3h * 100
        }

    def detect_range_trading(self, df: pd.DataFrame, periods: int = 50) -> Dict:
        """
        Detect range-bound trading opportunities

        Strategy: Buy at support, sell at resistance in consolidation
        Perfect for sideways/bear markets

        Args:
            df: DataFrame with price data
            periods: Lookback period for range detection

        Returns:
            Dictionary with range trading signal
        """
        if len(df) < periods:
            return {"signal": "neutral", "score": 0, "in_range": False}

        # Calculate range over period
        high_period = df['high'].iloc[-periods:].max()
        low_period = df['low'].iloc[-periods:].min()
        range_size = high_period - low_period
        current_close = df['close'].iloc[-1]

        # Is price in a range? (low volatility, no clear trend)
        ma_short = df['ma_short'].iloc[-1] if 'ma_short' in df.columns else current_close
        ma_long = df['ma_long'].iloc[-1] if 'ma_long' in df.columns else current_close
        ma_diff_pct = abs(ma_short - ma_long) / ma_long if ma_long > 0 else 1

        in_range = ma_diff_pct < 0.05  # MAs within 5% = ranging market

        if not in_range or range_size == 0:
            return {"signal": "neutral", "score": 0, "in_range": False}

        # Calculate position in range (0 = bottom, 1 = top)
        range_position = (current_close - low_period) / range_size

        score = 0
        signal = "neutral"

        # BUY at bottom of range
        if range_position < 0.25:  # In bottom 25% of range
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi < 40:
                score = 75
                signal = "buy"
            else:
                score = 50
                signal = "buy"

        # SELL at top of range
        elif range_position > 0.75:  # In top 25% of range
            rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
            if rsi > 60:
                score = 75
                signal = "sell"
            else:
                score = 50
                signal = "sell"

        return {
            "signal": signal,
            "score": score,
            "in_range": True,
            "range_position": range_position,
            "support": low_period,
            "resistance": high_period
        }

    def detect_dead_cat_bounce(self, df: pd.DataFrame) -> Dict:
        """
        Detect bear market rallies (dead cat bounces)

        Strategy: Catch quick bear market bounces with TIGHT stops
        High risk but can be profitable in strong downtrends

        Args:
            df: DataFrame with price data

        Returns:
            Dictionary with bounce signal
        """
        if len(df) < 30:
            return {"signal": "neutral", "score": 0}

        current_close = df['close'].iloc[-1]

        # Identify downtrend (bear market)
        ma_short = df['ma_short'].iloc[-1] if 'ma_short' in df.columns else current_close
        ma_long = df['ma_long'].iloc[-1] if 'ma_long' in df.columns else current_close
        in_downtrend = ma_short < ma_long

        if not in_downtrend:
            return {"signal": "neutral", "score": 0}

        # Recent sharp drop (creates bounce potential)
        price_7d_ago = df['close'].iloc[-168] if len(df) >= 168 else df['close'].iloc[0]  # 7 days in 1h candles
        drop_pct = (current_close - price_7d_ago) / price_7d_ago

        # RSI extreme oversold (bounce imminent)
        rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50

        # Volume spike (capitulation)
        volume_analysis = self.calculate_volume_analysis(df)

        score = 0
        signal = "neutral"

        # Perfect storm for bounce: downtrend + oversold + volume spike + big drop
        if drop_pct < -0.15 and rsi < 25 and volume_analysis['is_spike']:  # 15%+ drop
            score = 85
            signal = "buy"
        elif drop_pct < -0.10 and rsi < 30:  # 10%+ drop + oversold
            score = 65
            signal = "buy"
        elif in_downtrend and rsi < 25 and volume_analysis['is_spike']:  # Extreme oversold
            score = 50
            signal = "buy"

        return {
            "signal": signal,
            "score": score,
            "drop_pct": drop_pct * 100,
            "in_downtrend": in_downtrend,
            "rsi": rsi
        }
