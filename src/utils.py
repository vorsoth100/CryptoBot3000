"""
Utility functions for CryptoBot
Includes rate limiter, logging setup, and helper functions
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import deque
import pytz


class RateLimiter:
    """
    Rate limiter to respect API limits
    Tracks calls per minute and enforces delays
    """

    def __init__(self, calls_per_minute: int = 10):
        """
        Initialize rate limiter

        Args:
            calls_per_minute: Maximum API calls allowed per minute
        """
        self.calls_per_minute = calls_per_minute
        self.calls = deque()

    def wait_if_needed(self):
        """
        Wait if rate limit would be exceeded
        Removes calls older than 1 minute from tracking
        """
        now = time.time()

        # Remove calls older than 1 minute
        while self.calls and now - self.calls[0] > 60:
            self.calls.popleft()

        # If at limit, wait until oldest call expires
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                logging.debug(f"[RATE_LIMIT] Sleeping {sleep_time:.2f}s to respect rate limit")
                time.sleep(sleep_time)
                # Remove expired call
                self.calls.popleft()

        # Record this call
        self.calls.append(time.time())


def setup_logging(log_file: str = "logs/bot.log", level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration

    Args:
        log_file: Path to log file
        level: Logging level (DEBUG, INFO, WARN, ERROR)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("CryptoBot")
    logger.setLevel(getattr(logging, level.upper()))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, level.upper()))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def calculate_fees(trade_size_usd: float, maker_fee: float, taker_fee: float,
                   is_limit_order: bool = True) -> Dict[str, float]:
    """
    Calculate trading fees

    Args:
        trade_size_usd: Size of trade in USD
        maker_fee: Maker fee percentage (e.g., 0.005 for 0.5%)
        taker_fee: Taker fee percentage (e.g., 0.02 for 2%)
        is_limit_order: True for limit orders (maker), False for market (taker)

    Returns:
        Dictionary with fee breakdown
    """
    fee_rate = maker_fee if is_limit_order else taker_fee
    fee_amount = trade_size_usd * fee_rate
    net_amount = trade_size_usd - fee_amount

    return {
        "fee_rate": fee_rate,
        "fee_amount": fee_amount,
        "gross_amount": trade_size_usd,
        "net_amount": net_amount,
        "fee_type": "maker" if is_limit_order else "taker"
    }


def calculate_position_size(balance: float, position_pct: float,
                           maker_fee: float, taker_fee: float) -> float:
    """
    Calculate position size accounting for fees

    Args:
        balance: Available balance in USD
        position_pct: Percentage of balance to use (e.g., 0.20 for 20%)
        maker_fee: Maker fee percentage
        taker_fee: Taker fee percentage

    Returns:
        Position size in USD after fees
    """
    # Calculate target amount
    target_amount = balance * position_pct

    # Account for fees (use taker fee as worst case)
    # If we have $100 and want to buy, we can only get ~$98 worth after 2% fee
    position_size = target_amount / (1 + taker_fee)

    return position_size


def format_usd(amount: float) -> str:
    """Format USD amount for display"""
    return f"${amount:,.2f}"


def format_percentage(value: float) -> str:
    """Format percentage for display"""
    return f"{value * 100:.2f}%"


def utc_to_local(utc_dt: datetime, timezone: str = "America/New_York") -> datetime:
    """
    Convert UTC datetime to local timezone

    Args:
        utc_dt: UTC datetime
        timezone: Target timezone (default: America/New_York)

    Returns:
        Datetime in local timezone
    """
    utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
    local_tz = pytz.timezone(timezone)
    return utc_dt.astimezone(local_tz)


def calculate_break_even_price(entry_price: float, maker_fee: float,
                               taker_fee: float) -> float:
    """
    Calculate break-even price after fees

    Args:
        entry_price: Entry price per unit
        maker_fee: Maker fee percentage
        taker_fee: Taker fee percentage

    Returns:
        Break-even price (price needed to profit after buy + sell fees)
    """
    # When buying: pay entry_price * (1 + fee)
    # When selling: receive sell_price * (1 - fee)
    # Break-even when: sell_price * (1 - fee) = entry_price * (1 + fee)
    # Therefore: sell_price = entry_price * (1 + fee) / (1 - fee)

    # Use taker fee for worst case (market orders both ways)
    buy_cost_multiplier = 1 + taker_fee
    sell_net_multiplier = 1 - taker_fee

    break_even = entry_price * buy_cost_multiplier / sell_net_multiplier

    return break_even


def validate_config(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate configuration settings

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = [
        "initial_capital",
        "min_trade_usd",
        "max_positions",
        "max_position_pct",
        "stop_loss_pct",
        "coinbase_maker_fee",
        "coinbase_taker_fee"
    ]

    # Check required fields
    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"

    # Validate ranges
    if config["initial_capital"] <= 0:
        return False, "initial_capital must be positive"

    if config["min_trade_usd"] > config["initial_capital"]:
        return False, "min_trade_usd cannot exceed initial_capital"

    if not 0 < config["max_position_pct"] <= 1:
        return False, "max_position_pct must be between 0 and 1"

    if config["max_positions"] < 1:
        return False, "max_positions must be at least 1"

    if not 0 < config["stop_loss_pct"] < 1:
        return False, "stop_loss_pct must be between 0 and 1"

    return True, None


def get_timestamp() -> str:
    """Get current UTC timestamp as ISO string"""
    return datetime.utcnow().isoformat()


def calculate_pnl(entry_price: float, current_price: float, quantity: float,
                 entry_fee: float = 0, exit_fee: float = 0) -> Dict[str, float]:
    """
    Calculate profit/loss for a position

    Args:
        entry_price: Entry price per unit
        current_price: Current price per unit
        quantity: Position quantity
        entry_fee: Fee paid on entry
        exit_fee: Fee paid on exit (or estimated)

    Returns:
        Dictionary with P&L details
    """
    entry_value = entry_price * quantity
    current_value = current_price * quantity

    gross_pnl = current_value - entry_value
    net_pnl = gross_pnl - entry_fee - exit_fee

    pnl_pct = (net_pnl / (entry_value + entry_fee)) if entry_value > 0 else 0

    return {
        "entry_value": entry_value,
        "current_value": current_value,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "pnl_pct": pnl_pct,
        "total_fees": entry_fee + exit_fee
    }
