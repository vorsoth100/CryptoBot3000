"""
Main Trading Bot Engine for CryptoBot
Orchestrates all components and executes trading logic
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import sys

from src import __version__
from src.config_manager import ConfigManager
from src.coinbase_client import CoinbaseClient
from src.data_collector import DataCollector
from src.signals import SignalGenerator
from src.screener import MarketScreener
from src.risk_manager import RiskManager
from src.performance_tracker import PerformanceTracker
from src.claude_analyst import ClaudeAnalyst
from src.news_sentiment import NewsSentiment
from src.utils import setup_logging


class TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self, config_path: str = "data/config.json"):
        """
        Initialize trading bot

        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.get_all()

        # Setup logging
        log_level = self.config.get("log_level", "INFO")
        log_file = self.config.get("log_file", "logs/bot.log")
        self.logger = setup_logging(log_file, log_level)

        self.logger.info("=" * 80)
        self.logger.info(f"CryptoBot v{__version__} Starting...")
        self.logger.info("=" * 80)

        # Validate config
        is_valid, error = self.config_manager.validate()
        if not is_valid:
            self.logger.error(f"Invalid configuration: {error}")
            raise ValueError(f"Invalid configuration: {error}")

        # Initialize components
        self.coinbase = CoinbaseClient(
            sandbox=(self.config.get("coinbase_env") == "sandbox")
        )
        self.data_collector = DataCollector(
            self.coinbase,
            cache_minutes=self.config.get("screener_cache_minutes", 60)
        )
        self.signal_generator = SignalGenerator(self.config)
        self.news_sentiment = NewsSentiment(self.config)
        self.screener = MarketScreener(self.config, self.data_collector, self.signal_generator, self.news_sentiment)
        self.risk_manager = RiskManager(self.config, self.news_sentiment)
        self.performance_tracker = PerformanceTracker(self.config)
        self.claude_analyst = ClaudeAnalyst(self.config)

        # Bot state
        self.running = False
        self.dry_run = self.config.get("dry_run", True)
        self.last_analysis_time = None
        self.last_daily_reset = datetime.now().date()

        self.logger.info(f"Bot initialized in {'DRY RUN' if self.dry_run else 'LIVE'} mode")

    def start(self):
        """Start the trading bot"""
        self.running = True
        self.logger.info("Bot started")

        # Test connections
        if not self._test_connections():
            self.logger.error("Connection tests failed - stopping bot")
            return

        # Main loop
        try:
            while self.running:
                self._main_loop()
                self._sleep_until_next_check()

        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop the trading bot"""
        self.running = False
        self.logger.info("Bot stopped")

    def _test_connections(self) -> bool:
        """Test API connections"""
        self.logger.info("Testing API connections...")

        # Test Coinbase
        if not self.coinbase.test_connection():
            return False

        # Test Claude (optional)
        if self.config.get("claude_enabled"):
            try:
                # Simple test - just check if client exists
                if self.claude_analyst.client:
                    self.logger.info("✓ Claude API configured")
                else:
                    self.logger.warning("⚠ Claude API not configured")
            except Exception as e:
                self.logger.warning(f"⚠ Claude API test failed: {e}")

        return True

    def _main_loop(self):
        """Main bot loop iteration"""
        try:
            self.logger.info("=" * 80)
            self.logger.info(f"Bot check at {datetime.now().isoformat()}")
            self.logger.info("=" * 80)

            # Reset daily metrics if new day
            self._check_daily_reset()

            # Check existing positions for exit signals
            self._check_positions()

            # Run Claude analysis if scheduled
            if self._should_run_analysis():
                self._run_claude_analysis()

            # Look for new opportunities if we can open positions
            if len(self.risk_manager.positions) < self.config.get("max_positions", 3):
                self._scan_for_opportunities()

            # Save performance snapshot
            self.performance_tracker.save_performance_snapshot()

        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)

    def _check_daily_reset(self):
        """Reset daily metrics if new day"""
        today = datetime.now().date()
        if today > self.last_daily_reset:
            self.risk_manager.reset_daily_metrics()
            self.last_daily_reset = today
            self.logger.info("Daily metrics reset")

    def _check_positions(self):
        """Check all open positions for exit signals"""
        for product_id in list(self.risk_manager.positions.keys()):
            try:
                # Get current price
                current_price = self.data_collector.get_current_price(product_id, use_cache=False)
                if not current_price:
                    self.logger.warning(f"Could not get price for {product_id}")
                    continue

                # Check exit signals
                exit_signal = self.risk_manager.check_exit_signals(product_id, current_price)

                if exit_signal:
                    action, reason = exit_signal
                    self.logger.info(f"Exit signal for {product_id}: {action} - {reason}")

                    # Execute exit
                    self._close_position(product_id, current_price, reason)

                else:
                    # Log current P&L
                    pnl = self.risk_manager.get_position_pnl(product_id, current_price)
                    if pnl:
                        self.logger.info(
                            f"{product_id}: ${pnl['net_pnl']:.2f} ({pnl['pnl_pct']:.2f}%) "
                            f"| Price: ${current_price:.2f} | Stop: ${pnl['stop_loss_price']:.2f}"
                        )

            except Exception as e:
                self.logger.error(f"Error checking position {product_id}: {e}")

    def _close_position(self, product_id: str, current_price: float, reason: str):
        """Close a position"""
        try:
            position = self.risk_manager.positions.get(product_id)
            if not position:
                return

            # Calculate fees
            exit_value = current_price * position.quantity
            taker_fee = self.config.get("coinbase_taker_fee", 0.02)
            exit_fee = exit_value * taker_fee

            if not self.dry_run:
                # Execute market sell order
                order = self.coinbase.place_market_order(
                    product_id,
                    "SELL",
                    quantity=position.quantity
                )

                if not order:
                    self.logger.error(f"Failed to place sell order for {product_id}")
                    return

            # Close position in risk manager
            pnl_details = self.risk_manager.close_position(
                product_id,
                current_price,
                exit_fee,
                reason
            )

            # Log trade
            if pnl_details:
                self.performance_tracker.log_trade({
                    "product_id": product_id,
                    "side": "SELL",
                    "quantity": pnl_details['quantity'],
                    "price": current_price,
                    "value_usd": pnl_details['exit_value'],
                    "fee_usd": exit_fee,
                    "net_pnl": pnl_details['net_pnl'],
                    "pnl_pct": pnl_details['pnl_pct'],
                    "hold_time_hours": pnl_details['hold_time'],
                    "reason": reason,
                    "notes": "DRY RUN" if self.dry_run else "LIVE"
                })

        except Exception as e:
            self.logger.error(f"Error closing position {product_id}: {e}")

    def _should_run_analysis(self) -> bool:
        """Check if Claude analysis should run"""
        if not self.config.get("claude_enabled"):
            return False

        schedule = self.config.get("claude_analysis_schedule", "daily")

        if schedule == "disabled":
            return False

        # Check if enough time passed since last analysis
        if self.last_analysis_time:
            hours_since = (datetime.now() - self.last_analysis_time).total_seconds() / 3600

            if schedule == "daily" and hours_since < 24:
                return False
            elif schedule == "twice_daily" and hours_since < 12:
                return False
            elif schedule == "six_hourly" and hours_since < 6:
                return False

        # For six_hourly and twice_daily, run if no previous analysis or enough time passed
        if schedule in ["six_hourly", "twice_daily"]:
            if not self.last_analysis_time:
                return True
            # Time check already done above, don't run
            return False

        # Check if it's the scheduled time (for daily)
        if schedule == "daily":
            target_time = self.config.get("claude_analysis_time_utc", "00:00")
            target_hour = int(target_time.split(":")[0])
            current_hour = datetime.utcnow().hour

            # Run if we're in the target hour and haven't run today
            if current_hour == target_hour:
                today = datetime.now().date()
                if not self.last_analysis_time or self.last_analysis_time.date() < today:
                    return True

        return False

    def _run_claude_analysis(self):
        """Run Claude AI market analysis"""
        try:
            self.logger.info("Running Claude AI analysis...")

            # Build market context
            context = self._build_market_context()

            # Get analysis
            analysis = self.claude_analyst.analyze_market(context)

            if not analysis:
                self.logger.warning("No analysis received from Claude")
                return

            # Display analysis
            formatted = self.claude_analyst.format_analysis_for_display(analysis)
            self.logger.info(f"\n{formatted}")

            # Process recommendations
            if "recommended_actions" in analysis:
                for recommendation in analysis["recommended_actions"]:
                    self._process_claude_recommendation(recommendation)

            self.last_analysis_time = datetime.now()

        except Exception as e:
            self.logger.error(f"Error running Claude analysis: {e}")

    def _build_market_context(self) -> Dict:
        """Build market context for Claude analysis"""
        # Get portfolio
        if self.dry_run:
            balance = self.risk_manager.current_capital
        else:
            balance = self.coinbase.get_balance("USD")

        positions = self.risk_manager.get_all_positions()

        # Calculate total portfolio value (available capital + current position values)
        positions_value = 0.0
        for pos in positions:
            # Get current price for this position
            try:
                current_price = self.data_collector.get_current_price(pos["product_id"], use_cache=False)
                if current_price:
                    positions_value += pos["quantity"] * current_price
                else:
                    # Fallback to entry price if current price unavailable
                    positions_value += pos["quantity"] * pos["entry_price"]
            except Exception as e:
                self.logger.warning(f"Could not get current price for {pos['product_id']}, using entry price")
                positions_value += pos["quantity"] * pos["entry_price"]

        total_portfolio_value = balance + positions_value

        # Get market data
        screener_results = self.screener.screen_coins()

        # Get fear & greed
        fear_greed = self.data_collector.get_fear_greed_index()

        # Get BTC dominance
        btc_dominance = self.data_collector.get_btc_dominance()

        # Get news sentiment for screener results and key coins
        news_sentiment_data = {}
        if self.config.get("news_sentiment_enabled", False):
            try:
                # Pre-fetch all news ONCE to populate cache before looping
                # This prevents multiple simultaneous API calls
                self.news_sentiment._fetch_all_news()

                # Now get sentiment for top screener results (uses cached data)
                for opp in screener_results[:5]:  # Top 5 opportunities
                    sentiment = self.news_sentiment.get_sentiment(opp["product_id"])
                    if sentiment:
                        news_sentiment_data[opp["product_id"]] = {
                            "sentiment_score": sentiment["sentiment_score"],
                            "news_count": sentiment["news_count"],
                            "trending": sentiment["trending"],
                            "top_headline": sentiment["top_headlines"][0] if sentiment["top_headlines"] else ""
                        }

                # Get overall market sentiment summary
                market_news_summary = self.news_sentiment.get_sentiment_summary()
            except Exception as e:
                self.logger.error(f"Error fetching news sentiment: {e}")
                market_news_summary = "News sentiment unavailable"
        else:
            market_news_summary = "News sentiment disabled"

        # Get recent trades
        recent_trades = self.performance_tracker.get_all_trades()[-10:]

        # Get performance
        performance = self.performance_tracker.calculate_metrics()

        # Build detailed market snapshot with key coins
        market_snapshot = {}
        key_coins = ["BTC-USD", "ETH-USD", "SOL-USD"]

        for product_id in key_coins:
            try:
                # Don't use cache - get fresh prices
                price = self.data_collector.get_current_price(product_id, use_cache=False)
                if price:
                    market_snapshot[product_id] = {
                        "price": price,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    self.logger.warning(f"Could not get price for {product_id} - returned None")
            except Exception as e:
                self.logger.error(f"Error fetching price for {product_id}: {e}")

        return {
            "portfolio": {
                "balance_usd": balance,
                "positions": positions,
                "position_count": len(positions),
                "positions_value": positions_value,
                "total_value": total_portfolio_value,
                "initial_capital": self.risk_manager.initial_capital
            },
            "market_data": {
                "timestamp": datetime.now().isoformat(),
                "key_prices": market_snapshot
            },
            "screener_results": screener_results,
            "fear_greed": fear_greed,
            "btc_dominance": btc_dominance,
            "news_sentiment": news_sentiment_data,
            "market_news_summary": market_news_summary,
            "recent_trades": recent_trades,
            "performance": performance
        }

    def _process_claude_recommendation(self, recommendation: Dict):
        """Process a recommendation from Claude"""
        action = recommendation.get("action")
        product_id = recommendation.get("coin")

        if action == "buy":
            # Check if we should auto-execute
            if self.claude_analyst.should_execute_recommendation(recommendation):
                self.logger.info(f"Auto-executing Claude recommendation: BUY {product_id}")
                self._execute_buy(recommendation)
            else:
                self.logger.info(f"Advisory mode - not auto-executing BUY {product_id}")

        elif action == "sell":
            if product_id in self.risk_manager.positions:
                if self.claude_analyst.should_execute_recommendation(recommendation):
                    current_price = self.data_collector.get_current_price(product_id)
                    if current_price:
                        self._close_position(product_id, current_price, "Claude recommendation")
                else:
                    self.logger.info(f"Advisory mode - not auto-executing SELL {product_id}")

    def _scan_for_opportunities(self):
        """Scan market for trading opportunities"""
        try:
            self.logger.info("Scanning for opportunities...")

            # Run screener
            opportunities = self.screener.screen_coins()

            if not opportunities:
                self.logger.info("No opportunities found")
                return

            # Log top opportunities
            for i, opp in enumerate(opportunities[:3], 1):
                self.logger.info(
                    f"{i}. {opp['product_id']}: Score {opp['score']:.1f} | "
                    f"Signal: {opp['signal']} ({opp['confidence']:.0f}%) | "
                    f"Price: ${opp['price']:.2f}"
                )

            # Consider top opportunity
            top = opportunities[0]

            # Only act on strong signals
            if top['signal'] not in ['buy', 'strong_buy']:
                self.logger.info(f"Top opportunity not a buy signal: {top['signal']}")
                return

            # Check confidence
            if top['confidence'] < self.config.get("claude_confidence_threshold", 80):
                self.logger.info(f"Confidence too low: {top['confidence']:.0f}%")
                return

            # Execute if auto-trading enabled (would need Claude analysis first in real scenario)
            self.logger.info(f"Found opportunity but waiting for Claude analysis: {top['product_id']}")

        except Exception as e:
            self.logger.error(f"Error scanning opportunities: {e}")

    def _open_position(self, product_id: str, quantity: float, entry_price: float, reason: str = "Manual") -> tuple:
        """
        Open a new position (used by web UI and manual trades)

        Args:
            product_id: Product to buy (e.g., BTC-USD)
            quantity: Amount to buy (in base currency)
            entry_price: Price per unit
            reason: Reason for opening position

        Returns:
            Tuple of (success: bool, message: str, details: dict)
        """
        try:
            # Get current balance
            if self.dry_run:
                balance = self.risk_manager.current_capital
            else:
                balance = self.coinbase.get_balance("USD")
                if not balance:
                    self.logger.error("Could not get USD balance")
                    return False, "Could not get USD balance", {}

            # Calculate position size
            position_size_usd = quantity * entry_price

            # Calculate fee (use taker fee for market orders)
            taker_fee = self.config.get("coinbase_taker_fee", 0.02)
            entry_fee = position_size_usd * taker_fee
            fee_pct = taker_fee * 100

            # Check if can open position
            can_open, check_reason = self.risk_manager.can_open_position(product_id, position_size_usd, balance)
            if not can_open:
                self.logger.warning(f"Cannot open position: {check_reason}")
                # Return detailed error info
                return False, check_reason, {
                    "attempted_size_usd": position_size_usd,
                    "attempted_fee_pct": fee_pct,
                    "min_trade_usd": self.config.get("min_trade_usd", 0),
                    "max_fee_pct": self.config.get("max_fee_pct", 0) * 100,  # Convert to percentage for display
                    "max_positions": self.config.get("max_positions", 0),
                    "current_balance": balance,
                    "current_positions": len(self.risk_manager.get_all_positions())
                }

            if not self.dry_run:
                # Place market buy order
                order = self.coinbase.place_market_order(
                    product_id,
                    "BUY",
                    quantity=quantity
                )

                if not order:
                    self.logger.error(f"Failed to place order for {product_id}")
                    return False, "Failed to place order with exchange", {}

            # Open position in risk manager
            success = self.risk_manager.open_position(product_id, quantity, entry_price, entry_fee)

            if not success:
                self.logger.error(f"Risk manager rejected position")
                return False, "Risk manager rejected position", {}

            # Log trade
            self.performance_tracker.log_trade({
                "product_id": product_id,
                "side": "BUY",
                "quantity": quantity,
                "price": entry_price,
                "value_usd": position_size_usd,
                "fee_usd": entry_fee,
                "net_pnl": 0,
                "pnl_pct": 0,
                "hold_time_hours": 0,
                "reason": reason,
                "notes": "DRY RUN" if self.dry_run else "LIVE"
            })

            self.logger.info(f"✓ Opened position: {quantity:.6f} {product_id} @ ${entry_price:.2f} ({reason})")
            success_msg = f"Opened {quantity:.6f} {product_id} at ${entry_price:.2f} (${position_size_usd:.2f})"
            return True, success_msg, {"quantity": quantity, "entry_price": entry_price, "size_usd": position_size_usd}

        except Exception as e:
            self.logger.error(f"Error opening position: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error: {str(e)}", {}

    def _execute_buy(self, recommendation: Dict):
        """Execute a buy order from Claude recommendation"""
        try:
            product_id = recommendation.get("coin")
            target_price = recommendation.get("target_entry")

            # Get current balance
            if self.dry_run:
                balance = self.risk_manager.current_capital
            else:
                balance = self.coinbase.get_balance("USD")
                if not balance:
                    self.logger.error("Could not get USD balance")
                    return

            # Calculate position size
            position_size_usd = self.risk_manager.calculate_position_size_usd(balance)

            # Calculate quantity
            quantity = position_size_usd / target_price

            # Use the new _open_position method
            success, message, details = self._open_position(product_id, quantity, target_price, "Claude recommendation")
            if not success:
                self.logger.warning(f"Failed to execute Claude recommendation: {message}")

        except Exception as e:
            self.logger.error(f"Error executing buy: {e}")

    def _sleep_until_next_check(self):
        """Sleep until next check interval"""
        interval = self.config.get("check_interval_sec", 3600)
        self.logger.info(f"Sleeping for {interval}s until next check...")
        time.sleep(interval)

    def get_status(self) -> Dict:
        """Get current bot status"""
        # In dry run mode, use simulated capital from risk manager
        if self.dry_run:
            balance = self.risk_manager.current_capital
        else:
            balance = self.coinbase.get_balance("USD")

        positions = self.risk_manager.get_all_positions()
        metrics = self.performance_tracker.calculate_metrics()

        return {
            "running": self.running,
            "dry_run": self.dry_run,
            "balance_usd": balance,
            "initial_capital": self.config.get("initial_capital", 600),
            "positions": positions,
            "position_count": len(positions),
            "performance": metrics,
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None
        }


def main():
    """Main entry point"""
    bot = TradingBot()
    bot.start()


if __name__ == "__main__":
    main()
