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
