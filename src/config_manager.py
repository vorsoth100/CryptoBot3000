"""
Configuration Manager for CryptoBot
Handles loading, saving, and validating configuration
"""

import json
import os
from typing import Dict, Any, Optional
import logging
from copy import deepcopy


class ConfigManager:
    """Manages bot configuration with presets and validation"""

    DEFAULT_CONFIG = {
        # General Settings
        "coinbase_env": "live",
        "dry_run": True,
        "initial_capital": 600.0,
        "min_trade_usd": 150.0,
        "max_positions": 3,
        "max_position_pct": 0.25,
        "check_interval_sec": 3600,
        "verbose": True,

        # Fee Management
        "coinbase_maker_fee": 0.006,  # Bottom tier: 0.6%
        "coinbase_taker_fee": 0.008,  # Bottom tier: 0.8%
        "max_fee_pct": 0.01,  # Maximum acceptable: 1.0%
        "prefer_limit_orders": True,
        "limit_order_timeout_min": 60,
        "network_fee_buffer_usd": 10.0,

        # Risk Management
        "stop_loss_pct": 0.06,
        "take_profit_pct": 0.10,
        "trailing_stop_enabled": True,
        "trailing_stop_activation_pct": 0.10,
        "trailing_stop_distance_pct": 0.05,
        "max_drawdown_pct": 0.20,
        "max_daily_loss_pct": 0.05,
        "partial_profit_enabled": True,
        "partial_profit_levels": [0.10, 0.20, 0.30],
        "partial_profit_amounts": [0.33, 0.33, 0.34],

        # Market Screener
        "screener_enabled": True,
        "screener_mode": "breakouts",
        "screener_coins": [
            # Top Tier (Highest Liquidity)
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
            # Layer 1s
            "ADA-USD", "AVAX-USD", "DOT-USD", "ATOM-USD", "NEAR-USD",
            "APT-USD", "SUI-USD",
            # DeFi
            "LINK-USD", "UNI-USD", "AAVE-USD",
            # Layer 2s & Scaling
            "POL-USD", "ARB-USD", "OP-USD",  # POL is new MATIC ticker
            # AI & Gaming
            "RENDER-USD", "FET-USD", "GRT-USD",
            # Trending/Momentum
            "PEPE-USD", "DOGE-USD",
            # Established Alts
            "LTC-USD", "BCH-USD", "ETC-USD",
            # Staking/Yield
            "TIA-USD", "INJ-USD"
        ],
        "screener_min_market_cap": 5000000000,
        "screener_min_volume_24h": 500000000,
        "screener_max_results": 10,
        "screener_run_schedule": "daily",
        "screener_cache_minutes": 120,  # Increased to reduce CoinGecko API calls

        # Technical Indicators
        "use_talib": True,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "bb_period": 20,
        "bb_std": 2.0,
        "ma_short": 50,
        "ma_long": 200,
        "volume_spike_threshold": 2.0,

        # Claude AI Analyst
        "claude_enabled": True,
        "claude_analysis_mode": "semi_autonomous",  # Changed from advisory
        "claude_analysis_schedule": "six_hourly",  # Run every 6 hours
        "claude_analysis_time_utc": "00:00",
        "claude_confidence_threshold": 80,
        "claude_max_trade_suggestions": 3,
        "claude_risk_tolerance": "moderate",  # Changed from conservative
        "claude_include_fear_greed": True,
        "claude_include_btc_dominance": True,
        "claude_model": "claude-sonnet-4-5-20250929",

        # Market Regime Detection
        "regime_detection_enabled": True,
        "regime_indicator": "btc_dominance",
        "btc_dominance_bull_threshold": 45,
        "btc_dominance_bear_threshold": 55,
        "fear_greed_extreme_fear": 25,
        "fear_greed_extreme_greed": 75,
        "regime_check_interval_hours": 24,

        # News Sentiment (Crypto Panic)
        "news_sentiment_enabled": False,  # Disabled by default due to free tier rate limits
        "cryptopanic_api_key": "free",  # Use 'free' for public tier, or add your API key
        "news_sentiment_block_threshold": -30,  # Block trades if sentiment below this
        "news_sentiment_boost_threshold": 50,   # Boost score if sentiment above this
        "news_sentiment_cache_minutes": 360,    # Cache news for 6 hours (reduced API calls to 4/day max)
        "news_sentiment_lookback_hours": 24,    # Analyze last 24 hours of news

        # CoinGecko Data (Free tier - no API key required)
        "coingecko_enabled": True,           # Enable CoinGecko trending and social data
        "coingecko_cache_minutes": 10,       # Cache coin data for 10 minutes
        "coingecko_trending_boost": 5,       # Score boost for trending coins
        "coingecko_sentiment_boost": 3,      # Score boost for positive sentiment (>70%)
        "coingecko_social_boost": 2,         # Score boost for high social activity

        # LunarCrush Social Sentiment (Free tier - no API key required for v2)
        "lunarcrush_enabled": True,          # Enable LunarCrush social sentiment analysis
        "lunarcrush_cache_minutes": 30,      # Cache social data for 30 minutes
        "lunarcrush_galaxy_score_min": 50,   # Minimum Galaxy Score for trade consideration (0-100)
        "lunarcrush_social_volume_boost": 5, # Score boost for high social volume
        "lunarcrush_sentiment_boost": 3,     # Score boost for positive sentiment
        "lunarcrush_alt_rank_boost": 4,      # Score boost for top AltRank coins

        # Telegram Bot Integration
        "telegram_enabled": False,           # Enable Telegram notifications and bot commands
        "telegram_bot_token": "",            # Get from @BotFather on Telegram
        "telegram_chat_id": "",              # Your Telegram chat ID
        "telegram_notify_trades": True,      # Notify on trade entries/exits
        "telegram_notify_stop_loss": True,   # Notify on stop loss hits
        "telegram_notify_take_profit": True, # Notify on take profit hits
        "telegram_notify_claude": True,      # Notify on Claude analysis
        "telegram_notify_errors": True,      # Notify on errors
        "telegram_daily_summary": True,      # Send daily performance summary

        # TradingView Webhook Integration
        "tradingview_webhook_enabled": False,    # Enable TradingView webhook signals
        "tradingview_webhook_secret": "",        # Secret key for webhook authentication
        "tradingview_auto_trade": False,         # Automatically execute TradingView signals
        "tradingview_require_confirmation": True, # Require signal confirmation with indicators

        # Notifications
        "email_enabled": False,
        "email_address": "",
        "email_on_trade": True,
        "email_on_stop_loss": True,
        "email_on_take_profit": True,
        "email_on_error": True,
        "email_daily_summary": True,

        # Logging & Debug
        "log_file": "logs/bot.log",
        "trade_log_file": "logs/trades.csv",
        "performance_file": "logs/performance.json",
        "claude_log_file": "logs/claude_analysis.log",
        "log_level": "INFO"
    }

    PRESETS = {
        "conservative": {
            "max_positions": 2,
            "max_position_pct": 0.20,
            "stop_loss_pct": 0.07,
            "take_profit_pct": 0.12,
            "claude_confidence_threshold": 85,
            "claude_max_trade_suggestions": 2,
            "claude_risk_tolerance": "conservative",
            "screener_mode": "support",
            "max_daily_loss_pct": 0.03
        },
        "moderate": {
            "max_positions": 3,
            "max_position_pct": 0.25,
            "stop_loss_pct": 0.06,
            "take_profit_pct": 0.10,
            "claude_confidence_threshold": 75,
            "claude_max_trade_suggestions": 3,
            "claude_risk_tolerance": "moderate",
            "screener_mode": "breakouts",
            "max_daily_loss_pct": 0.05
        },
        "aggressive": {
            "max_positions": 4,
            "max_position_pct": 0.25,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.08,
            "claude_confidence_threshold": 70,
            "claude_max_trade_suggestions": 4,
            "claude_risk_tolerance": "aggressive",
            "screener_mode": "trending",
            "max_daily_loss_pct": 0.07
        }
    }

    def __init__(self, config_path: str = "data/config.json"):
        """
        Initialize configuration manager

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config = deepcopy(self.DEFAULT_CONFIG)
        self.logger = logging.getLogger("CryptoBot.Config")

        # Load config if exists
        if os.path.exists(config_path):
            self.load()
        else:
            self.logger.info(f"No config found at {config_path}, using defaults")
            self.save()

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file

        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_path, 'r') as f:
                loaded_config = json.load(f)

            # Merge with defaults (in case new fields were added)
            self.config = deepcopy(self.DEFAULT_CONFIG)
            self.config.update(loaded_config)

            self.logger.info(f"Loaded config from {self.config_path}")
            return self.config

        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            self.logger.info("Using default configuration")
            return self.config

    def save(self) -> bool:
        """
        Save configuration to file

        Returns:
            True if successful
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            self.logger.info(f"Saved config to {self.config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value

        Args:
            key: Configuration key
            value: New value

        Returns:
            True if successful
        """
        try:
            self.config[key] = value
            self.logger.info(f"Updated config: {key} = {value}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting config {key}: {e}")
            return False

    def update(self, updates: Dict[str, Any]) -> bool:
        """
        Update multiple configuration values

        Args:
            updates: Dictionary of key-value pairs to update

        Returns:
            True if successful
        """
        try:
            self.config.update(updates)
            self.logger.info(f"Updated {len(updates)} config values")
            return True
        except Exception as e:
            self.logger.error(f"Error updating config: {e}")
            return False

    def apply_preset(self, preset_name: str) -> bool:
        """
        Apply a configuration preset

        Args:
            preset_name: Name of preset (conservative, moderate, aggressive)

        Returns:
            True if successful
        """
        if preset_name not in self.PRESETS:
            self.logger.error(f"Unknown preset: {preset_name}")
            return False

        try:
            preset = self.PRESETS[preset_name]
            self.config.update(preset)
            self.logger.info(f"Applied {preset_name} preset")
            return True

        except Exception as e:
            self.logger.error(f"Error applying preset: {e}")
            return False

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate current configuration

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        required_fields = [
            "initial_capital", "min_trade_usd", "max_positions",
            "max_position_pct", "stop_loss_pct", "coinbase_maker_fee",
            "coinbase_taker_fee"
        ]

        for field in required_fields:
            if field not in self.config:
                return False, f"Missing required field: {field}"

        # Validate ranges
        if self.config["initial_capital"] <= 0:
            return False, "initial_capital must be positive"

        if self.config["min_trade_usd"] > self.config["initial_capital"]:
            return False, "min_trade_usd cannot exceed initial_capital"

        if not 0 < self.config["max_position_pct"] <= 1:
            return False, "max_position_pct must be between 0 and 1"

        if self.config["max_positions"] < 1:
            return False, "max_positions must be at least 1"

        if not 0 < self.config["stop_loss_pct"] < 1:
            return False, "stop_loss_pct must be between 0 and 1"

        if not 0 < self.config["max_drawdown_pct"] < 1:
            return False, "max_drawdown_pct must be between 0 and 1"

        # Validate partial profit settings
        if self.config["partial_profit_enabled"]:
            levels = self.config["partial_profit_levels"]
            amounts = self.config["partial_profit_amounts"]

            if len(levels) != len(amounts):
                return False, "partial_profit_levels and amounts must be same length"

            if abs(sum(amounts) - 1.0) > 0.01:
                return False, "partial_profit_amounts must sum to 1.0"

        return True, None

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration dictionary"""
        return deepcopy(self.config)

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults"""
        try:
            self.config = deepcopy(self.DEFAULT_CONFIG)
            self.logger.info("Reset config to defaults")
            return True
        except Exception as e:
            self.logger.error(f"Error resetting config: {e}")
            return False

    def export_to_file(self, filepath: str) -> bool:
        """
        Export configuration to a file

        Args:
            filepath: Path to export file

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Exported config to {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting config: {e}")
            return False

    def import_from_file(self, filepath: str) -> bool:
        """
        Import configuration from a file

        Args:
            filepath: Path to import file

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'r') as f:
                imported_config = json.load(f)

            # Validate imported config
            temp_config = deepcopy(self.DEFAULT_CONFIG)
            temp_config.update(imported_config)

            # Temporarily set and validate
            old_config = self.config
            self.config = temp_config
            is_valid, error = self.validate()

            if not is_valid:
                self.config = old_config
                self.logger.error(f"Invalid imported config: {error}")
                return False

            self.logger.info(f"Imported config from {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error importing config: {e}")
            return False
