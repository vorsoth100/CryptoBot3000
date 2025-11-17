"""
Telegram Bot Integration for CryptoBot
Provides notifications and bot control via Telegram
"""

import logging
import asyncio
from typing import Dict, Optional, Callable
from datetime import datetime
import pytz

try:
    from telegram import Update, Bot
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.constants import ParseMode
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramNotifier:
    """Handles Telegram notifications and bot commands"""

    def __init__(self, config: Dict, bot_controller: Optional[Callable] = None):
        """
        Initialize Telegram notifier

        Args:
            config: Configuration dictionary
            bot_controller: Optional callback to control main trading bot
        """
        self.config = config
        self.bot_controller = bot_controller
        self.logger = logging.getLogger("CryptoBot.Telegram")
        self.timezone = pytz.timezone('US/Eastern')

        if not TELEGRAM_AVAILABLE:
            self.logger.warning("python-telegram-bot not installed. Telegram features disabled.")
            self.enabled = False
            self.bot = None
            self.application = None
            return

        self.enabled = config.get("telegram_enabled", False)
        self.bot_token = config.get("telegram_bot_token", "")
        self.chat_id = config.get("telegram_chat_id", "")

        if not self.enabled or not self.bot_token or not self.chat_id:
            self.logger.info("Telegram notifications disabled in config")
            self.bot = None
            self.application = None
            return

        # Initialize bot
        try:
            self.bot = Bot(token=self.bot_token)
            self.application = Application.builder().token(self.bot_token).build()

            # Register command handlers
            self._register_commands()

            self.logger.info("Telegram bot initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram bot: {e}")
            self.enabled = False
            self.bot = None
            self.application = None

    def _register_commands(self):
        """Register bot command handlers"""
        if not self.application:
            return

        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("pause", self._cmd_pause))
        self.application.add_handler(CommandHandler("resume", self._cmd_resume))
        self.application.add_handler(CommandHandler("positions", self._cmd_positions))
        self.application.add_handler(CommandHandler("performance", self._cmd_performance))

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_msg = (
            "🤖 *CryptoBot3000 Telegram Bot*\n\n"
            "I'll send you notifications about:\n"
            "• Trade executions (entry/exit)\n"
            "• Performance updates\n"
            "• Stop loss & take profit hits\n"
            "• Claude AI analysis\n"
            "• Alerts and errors\n\n"
            "Use /help to see available commands."
        )
        await update.message.reply_text(welcome_msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_msg = (
            "*Available Commands:*\n\n"
            "/status - Show bot status and current mode\n"
            "/positions - Show active positions\n"
            "/performance - Show performance metrics\n"
            "/pause - Pause trading bot\n"
            "/resume - Resume trading bot\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(help_msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.bot_controller:
            await update.message.reply_text("❌ Bot controller not available")
            return

        try:
            status = self.bot_controller("get_status")
            status_msg = (
                f"*Bot Status*\n\n"
                f"Running: {'✅ Yes' if status.get('running') else '❌ No'}\n"
                f"Mode: {status.get('mode', 'Unknown')}\n"
                f"Active Positions: {status.get('positions', 0)}\n"
                f"Last Check: {status.get('last_check', 'N/A')}"
            )
            await update.message.reply_text(status_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting status: {e}")

    async def _cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pause command"""
        if not self.bot_controller:
            await update.message.reply_text("❌ Bot controller not available")
            return

        try:
            self.bot_controller("pause")
            await update.message.reply_text("⏸️ Trading bot paused")
        except Exception as e:
            await update.message.reply_text(f"❌ Error pausing bot: {e}")

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        if not self.bot_controller:
            await update.message.reply_text("❌ Bot controller not available")
            return

        try:
            self.bot_controller("resume")
            await update.message.reply_text("▶️ Trading bot resumed")
        except Exception as e:
            await update.message.reply_text(f"❌ Error resuming bot: {e}")

    async def _cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        if not self.bot_controller:
            await update.message.reply_text("❌ Bot controller not available")
            return

        try:
            positions = self.bot_controller("get_positions")
            if not positions:
                await update.message.reply_text("No active positions")
                return

            msg = "*Active Positions:*\n\n"
            for pos in positions:
                msg += (
                    f"*{pos['symbol']}*\n"
                    f"  Entry: ${pos['entry_price']:.2f}\n"
                    f"  Current: ${pos['current_price']:.2f}\n"
                    f"  P&L: {pos['pnl']:+.2f}%\n\n"
                )
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting positions: {e}")

    async def _cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /performance command"""
        if not self.bot_controller:
            await update.message.reply_text("❌ Bot controller not available")
            return

        try:
            perf = self.bot_controller("get_performance")
            msg = (
                f"*Performance Summary*\n\n"
                f"Total Return: {perf.get('total_return', 0):+.2f}%\n"
                f"Win Rate: {perf.get('win_rate', 0):.1f}%\n"
                f"Total Trades: {perf.get('total_trades', 0)}\n"
                f"Profit Factor: {perf.get('profit_factor', 0):.2f}"
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting performance: {e}")

    async def _send_message_async(self, message: str, parse_mode: Optional[str] = ParseMode.MARKDOWN):
        """Send message asynchronously"""
        if not self.enabled or not self.bot or not self.chat_id:
            return

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")

    def send_message(self, message: str, parse_mode: Optional[str] = ParseMode.MARKDOWN):
        """Send message (synchronous wrapper)"""
        if not self.enabled:
            return

        try:
            # Create new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(self._send_message_async(message, parse_mode))
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")

    def notify_trade_entry(self, symbol: str, side: str, price: float, size: float, reason: str = ""):
        """Send trade entry notification"""
        emoji = "🟢" if side.upper() == "BUY" else "🔴"
        msg = (
            f"{emoji} *Trade Entry*\n\n"
            f"Symbol: {symbol}\n"
            f"Side: {side.upper()}\n"
            f"Price: ${price:.2f}\n"
            f"Size: {size:.4f}\n"
        )
        if reason:
            msg += f"Reason: {reason}\n"
        msg += f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        self.send_message(msg)

    def notify_trade_exit(self, symbol: str, side: str, entry_price: float, exit_price: float,
                         pnl: float, pnl_pct: float, reason: str = ""):
        """Send trade exit notification"""
        emoji = "✅" if pnl > 0 else "❌"
        msg = (
            f"{emoji} *Trade Exit*\n\n"
            f"Symbol: {symbol}\n"
            f"Side: {side.upper()}\n"
            f"Entry: ${entry_price:.2f}\n"
            f"Exit: ${exit_price:.2f}\n"
            f"P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)\n"
        )
        if reason:
            msg += f"Reason: {reason}\n"
        msg += f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        self.send_message(msg)

    def notify_stop_loss(self, symbol: str, entry_price: float, stop_price: float, loss: float):
        """Send stop loss notification"""
        msg = (
            f"🛑 *Stop Loss Hit*\n\n"
            f"Symbol: {symbol}\n"
            f"Entry: ${entry_price:.2f}\n"
            f"Stop: ${stop_price:.2f}\n"
            f"Loss: ${loss:.2f}\n"
            f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        self.send_message(msg)

    def notify_take_profit(self, symbol: str, entry_price: float, target_price: float, profit: float):
        """Send take profit notification"""
        msg = (
            f"🎯 *Take Profit Hit*\n\n"
            f"Symbol: {symbol}\n"
            f"Entry: ${entry_price:.2f}\n"
            f"Target: ${target_price:.2f}\n"
            f"Profit: ${profit:.2f}\n"
            f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        self.send_message(msg)

    def notify_claude_analysis(self, summary: str, top_picks: list):
        """Send Claude AI analysis notification"""
        msg = (
            f"🤖 *Claude AI Analysis*\n\n"
            f"{summary}\n\n"
            f"*Top Picks:*\n"
        )
        for i, pick in enumerate(top_picks[:3], 1):
            msg += f"{i}. {pick}\n"
        msg += f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        self.send_message(msg)

    def notify_daily_summary(self, total_return: float, trades: int, win_rate: float,
                            best_trade: str = "", worst_trade: str = ""):
        """Send daily performance summary"""
        emoji = "📈" if total_return >= 0 else "📉"
        msg = (
            f"{emoji} *Daily Summary*\n\n"
            f"Return: {total_return:+.2f}%\n"
            f"Trades: {trades}\n"
            f"Win Rate: {win_rate:.1f}%\n"
        )
        if best_trade:
            msg += f"Best: {best_trade}\n"
        if worst_trade:
            msg += f"Worst: {worst_trade}\n"
        msg += f"\nDate: {datetime.now(self.timezone).strftime('%Y-%m-%d')}"
        self.send_message(msg)

    def notify_error(self, error_msg: str):
        """Send error notification"""
        msg = (
            f"⚠️ *Error Alert*\n\n"
            f"{error_msg}\n"
            f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        self.send_message(msg)

    def notify_alert(self, alert_msg: str):
        """Send general alert notification"""
        msg = (
            f"🔔 *Alert*\n\n"
            f"{alert_msg}\n"
            f"\nTime: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        self.send_message(msg)

    def start_polling(self):
        """Start bot polling (for command handling)"""
        if not self.enabled or not self.application:
            return

        try:
            self.logger.info("Starting Telegram bot polling...")
            self.application.run_polling()
        except Exception as e:
            self.logger.error(f"Error in Telegram bot polling: {e}")

    def stop(self):
        """Stop Telegram bot"""
        if self.application:
            try:
                self.application.stop()
                self.logger.info("Telegram bot stopped")
            except Exception as e:
                self.logger.error(f"Error stopping Telegram bot: {e}")
