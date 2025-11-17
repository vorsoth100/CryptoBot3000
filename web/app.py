"""
Flask Web Application for CryptoBot
Provides web dashboard for monitoring and control
"""

import os
import sys
import json
import threading
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from datetime import datetime
import pytz

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading_bot import TradingBot
from src.config_manager import ConfigManager
from src import __version__

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cryptobot-secret-key-change-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Set timezone to US Eastern
EASTERN = pytz.timezone('US/Eastern')

# Configure logging with Eastern timezone
class EasternFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, EASTERN)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S %Z')

# Global bot instance
bot = None
bot_thread = None


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html', version=__version__)


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now(EASTERN).isoformat(), "version": __version__})


@app.route('/api/status')
def get_status():
    """Get bot status"""
    if bot:
        status = bot.get_status()
        status['version'] = __version__
        return jsonify(status)
    else:
        return jsonify({"running": False, "error": "Bot not initialized", "version": __version__})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config_manager = ConfigManager()
    return jsonify(config_manager.get_all())


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        updates = request.json
        config_manager = ConfigManager()
        config_manager.update(updates)
        config_manager.save()

        # If bot is running, reload its config
        if bot:
            bot.config_manager.load()
            bot.config = bot.config_manager.get_all()

        return jsonify({"success": True, "message": "Configuration updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/config/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults"""
    try:
        import os
        config_path = "data/config.json"

        # Backup old config
        if os.path.exists(config_path):
            backup_path = f"{config_path}.backup"
            os.rename(config_path, backup_path)

        # Reload default config
        config_manager = ConfigManager()
        config_manager.save()

        # If bot is running, reload its config
        if bot:
            bot.config_manager.load()
            bot.config = bot.config_manager.get_all()

        return jsonify({"success": True, "message": "Configuration reset to defaults"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/preset/<preset_name>', methods=['POST'])
def apply_preset(preset_name):
    """Apply configuration preset"""
    try:
        config_manager = ConfigManager()
        success = config_manager.apply_preset(preset_name)

        if success:
            config_manager.save()
            return jsonify({"success": True, "message": f"Applied {preset_name} preset"})
        else:
            return jsonify({"success": False, "error": "Invalid preset"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the trading bot"""
    global bot, bot_thread

    if bot and bot.running:
        return jsonify({"success": False, "error": "Bot already running"}), 400

    try:
        bot = TradingBot()

        # Start bot in separate thread
        bot_thread = threading.Thread(target=bot.start)
        bot_thread.daemon = True
        bot_thread.start()

        return jsonify({"success": True, "message": "Bot started"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the trading bot"""
    global bot

    if not bot or not bot.running:
        return jsonify({"success": False, "error": "Bot not running"}), 400

    try:
        bot.stop()
        return jsonify({"success": True, "message": "Bot stopped"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/positions')
def get_positions():
    """Get all open positions"""
    if bot:
        positions = bot.risk_manager.get_all_positions()

        # Add current P&L for each position
        positions_with_pnl = []
        for pos in positions:
            current_price = bot.data_collector.get_current_price(pos['product_id'])
            if current_price:
                pnl = bot.risk_manager.get_position_pnl(pos['product_id'], current_price)
                if pnl:
                    pos.update(pnl)

            positions_with_pnl.append(pos)

        return jsonify(positions_with_pnl)
    else:
        return jsonify([])


@app.route('/api/trades')
def get_trades():
    """Get trade history"""
    if bot:
        trades = bot.performance_tracker.get_all_trades()
        return jsonify(trades)
    else:
        return jsonify([])


@app.route('/api/performance')
def get_performance():
    """Get performance metrics"""
    if bot:
        metrics = bot.performance_tracker.calculate_metrics()
        return jsonify(metrics)
    else:
        return jsonify({})


@app.route('/api/balance')
def get_balance():
    """Get account balance"""
    if bot:
        # In dry run mode, use simulated capital
        if bot.dry_run:
            # Get current capital from risk manager (tracks simulated balance)
            balance = bot.risk_manager.current_capital
        else:
            # Live mode - get actual Coinbase balance
            balance = bot.coinbase.get_balance("USD")

        return jsonify({
            "balance_usd": balance,
            "dry_run": bot.dry_run
        })
    else:
        return jsonify({"balance_usd": 0, "dry_run": True})


@app.route('/api/screener')
def run_screener():
    """Run market screener or get latest automated results"""
    if not bot:
        return jsonify([])

    try:
        import logging
        import json
        import os
        from src.claude_analyst import convert_numpy_types
        logger = logging.getLogger("CryptoBot.Web")

        # Check if we have recent automated results (within last hour)
        automated_file = "data/latest_screener.json"
        if os.path.exists(automated_file):
            from datetime import datetime, timedelta
            file_time = datetime.fromtimestamp(os.path.getmtime(automated_file))
            if datetime.now() - file_time < timedelta(hours=1):
                # Return automated results
                with open(automated_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Returning automated screener results from {data['timestamp']}")
                return jsonify(data['opportunities'])

        # Otherwise run manual screener
        logger.info("Running screener via API...")
        opportunities = bot.screener.screen_coins()
        logger.info(f"Screener found {len(opportunities)} opportunities")

        if opportunities:
            for i, opp in enumerate(opportunities[:3], 1):
                logger.info(f"  {i}. {opp['product_id']}: {opp['signal']} (score: {opp['score']:.1f}, confidence: {opp['confidence']:.0f}%)")

        # Convert numpy types to native Python types for JSON serialization
        clean_opportunities = convert_numpy_types(opportunities)

        return jsonify(clean_opportunities)

    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger("CryptoBot.Web")
        error_details = traceback.format_exc()
        logger.error(f"Screener error: {e}")
        logger.error(f"Traceback:\n{error_details}")
        return jsonify({"error": str(e), "details": "Check bot logs for full traceback"}), 500


@app.route('/api/claude/latest')
def get_latest_claude_analysis():
    """Get latest automated Claude analysis"""
    try:
        import json
        import os
        from datetime import datetime, timedelta

        automated_file = "data/latest_claude_analysis.json"
        if os.path.exists(automated_file):
            with open(automated_file, 'r') as f:
                data = json.load(f)
            return jsonify({"success": True, "analysis": data['analysis'], "timestamp": data['timestamp']})
        else:
            return jsonify({"success": False, "error": "No automated analysis available yet"}), 404

    except Exception as e:
        import logging
        logger = logging.getLogger("CryptoBot.Web")
        logger.error(f"Error loading latest Claude analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/claude/analyze', methods=['POST'])
def run_claude_analysis():
    """Trigger manual Claude AI analysis"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        import logging
        logger = logging.getLogger("CryptoBot.Web")

        logger.info("Building market context for Claude analysis...")
        context = bot._build_market_context()
        logger.info(f"Context built successfully with keys: {list(context.keys())}")

        # Log detailed context info
        logger.info(f"Portfolio balance: ${context.get('portfolio', {}).get('balance_usd', 0):.2f}")
        logger.info(f"Positions: {context.get('portfolio', {}).get('position_count', 0)}")
        logger.info(f"Market data keys: {list(context.get('market_data', {}).keys())}")
        logger.info(f"Key prices available: {list(context.get('market_data', {}).get('key_prices', {}).keys())}")
        logger.info(f"Screener results count: {len(context.get('screener_results', []))}")
        if context.get('screener_results'):
            logger.info(f"Top screener result: {context['screener_results'][0].get('product_id')} - {context['screener_results'][0].get('signal')}")
        logger.info(f"Fear & Greed: {context.get('fear_greed', {})}")
        logger.info(f"BTC Dominance: {context.get('btc_dominance')}")

        logger.info("Requesting Claude analysis...")
        analysis = bot.claude_analyst.analyze_market(context)
        logger.info(f"Analysis result type: {type(analysis)}")

        if analysis:
            logger.info("✓ Claude analysis completed successfully")
            return jsonify({"success": True, "analysis": analysis})
        else:
            logger.error("✗ Claude analysis returned None")
            return jsonify({"success": False, "error": "Analysis returned empty result"}), 500

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger = logging.getLogger("CryptoBot.Web")
        logger.error(f"Claude analysis error: {e}")
        logger.error(f"Traceback:\n{error_details}")
        return jsonify({"success": False, "error": f"{str(e)} - Check logs for details"}), 500


@app.route('/api/trade/execute', methods=['POST'])
def execute_trade():
    """Execute a Claude-recommended trade"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        data = request.json
        product_id = data.get('product_id')
        position_size_pct = data.get('position_size_pct')
        stop_loss = data.get('stop_loss')
        take_profit = data.get('take_profit')

        if not all([product_id, position_size_pct, stop_loss, take_profit]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # Get current price
        current_price = bot.data_collector.get_current_price(product_id)
        if not current_price:
            return jsonify({"success": False, "error": "Could not get current price"}), 400

        # Calculate position size in USD
        capital = bot.risk_manager.current_capital
        size_usd = capital * position_size_pct

        # Calculate quantity
        quantity = size_usd / current_price

        # Open position
        success, message, details = bot._open_position(product_id, quantity, current_price, "Claude recommendation")

        if success:
            return jsonify({
                "success": True,
                "message": message
            })
        else:
            return jsonify({
                "success": False,
                "error": message,
                "details": details
            }), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/preview', methods=['POST'])
def preview_trade():
    """Preview a manual trade with full breakdown"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        data = request.json
        product_id = data.get('product_id')
        size_usd = data.get('size_usd')
        stop_loss_pct = data.get('stop_loss_pct')
        take_profit_pct = data.get('take_profit_pct')

        if not all([product_id, size_usd]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # Get current price
        current_price = bot.data_collector.get_current_price(product_id)
        if not current_price:
            return jsonify({"success": False, "error": "Could not get current price"}), 400

        # Calculate trade breakdown
        taker_fee_rate = bot.config.get("coinbase_taker_fee", 0.008)
        fee_amount = size_usd * taker_fee_rate
        quantity = size_usd / current_price

        # Calculate stop loss and take profit prices
        stop_loss_price = current_price * (1 - stop_loss_pct) if stop_loss_pct else None
        take_profit_price = current_price * (1 + take_profit_pct) if take_profit_pct else None

        # Total cost (trade size + fees)
        total_cost = size_usd + fee_amount

        return jsonify({
            "success": True,
            "preview": {
                "product_id": product_id,
                "current_price": current_price,
                "trade_size_usd": size_usd,
                "quantity": quantity,
                "fee_rate_pct": taker_fee_rate * 100,
                "fee_amount_usd": fee_amount,
                "total_cost_usd": total_cost,
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price,
                "stop_loss_pct": stop_loss_pct * 100 if stop_loss_pct else 0,
                "take_profit_pct": take_profit_pct * 100 if take_profit_pct else 0
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trade/manual', methods=['POST'])
def manual_trade():
    """Execute a manual trade"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        data = request.json
        product_id = data.get('product_id')
        size_usd = data.get('size_usd')
        stop_loss_pct = data.get('stop_loss_pct')
        take_profit_pct = data.get('take_profit_pct')

        if not all([product_id, size_usd, stop_loss_pct, take_profit_pct]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        # Get current price
        current_price = bot.data_collector.get_current_price(product_id)
        if not current_price:
            return jsonify({"success": False, "error": "Could not get current price"}), 400

        # Calculate quantity
        quantity = size_usd / current_price

        # Open position
        success, message, details = bot._open_position(product_id, quantity, current_price, "Manual entry")

        if success:
            return jsonify({
                "success": True,
                "message": f"{message}\nStop Loss: {stop_loss_pct*100:.1f}% | Take Profit: {take_profit_pct*100:.1f}%"
            })
        else:
            return jsonify({
                "success": False,
                "error": message,
                "details": details
            }), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/position/close/<product_id>', methods=['POST'])
def close_position(product_id):
    """Manually close a position"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        current_price = bot.data_collector.get_current_price(product_id)
        if not current_price:
            return jsonify({"success": False, "error": "Could not get current price"}), 400

        bot._close_position(product_id, current_price, "Manual close")

        return jsonify({"success": True, "message": f"Closed {product_id}"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/recommendations/past', methods=['GET'])
def get_past_recommendations():
    """Get past recommendations from file"""
    try:
        past_recs_file = "data/past_recommendations.json"
        if os.path.exists(past_recs_file):
            with open(past_recs_file, 'r') as f:
                data = json.load(f)
            return jsonify({"success": True, "recommendations": data})
        else:
            return jsonify({"success": True, "recommendations": []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/recommendations/past', methods=['POST'])
def save_past_recommendation():
    """Save a past recommendation to file"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        past_recs_file = "data/past_recommendations.json"

        # Load existing recommendations
        if os.path.exists(past_recs_file):
            with open(past_recs_file, 'r') as f:
                past_recs = json.load(f)
        else:
            past_recs = []

        # Add new recommendation at the beginning
        past_recs.insert(0, data)

        # Keep only last 50
        past_recs = past_recs[:50]

        # Save back to file
        os.makedirs("data", exist_ok=True)
        with open(past_recs_file, 'w') as f:
            json.dump(past_recs, f, indent=2)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/recommendations/past', methods=['DELETE'])
def clear_past_recommendations():
    """Clear all past recommendations"""
    try:
        past_recs_file = "data/past_recommendations.json"

        # Write empty array to file
        os.makedirs("data", exist_ok=True)
        with open(past_recs_file, 'w') as f:
            json.dump([], f, indent=2)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test/coinbase', methods=['POST'])
def test_coinbase():
    """Test Coinbase API connection"""
    try:
        from src.coinbase_client import CoinbaseClient

        client = CoinbaseClient()
        success = client.test_connection()

        if success:
            balance = client.get_balance("USD")
            return jsonify({
                "success": True,
                "message": "Coinbase connection successful",
                "balance_usd": balance
            })
        else:
            return jsonify({"success": False, "error": "Connection test failed"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test/claude', methods=['POST'])
def test_claude():
    """Test Claude API connection"""
    try:
        config_manager = ConfigManager()
        from src.claude_analyst import ClaudeAnalyst

        analyst = ClaudeAnalyst(config_manager.get_all())

        if analyst.client:
            return jsonify({
                "success": True,
                "message": "Claude API configured",
                "model": analyst.model
            })
        else:
            return jsonify({"success": False, "error": "API key not configured"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test/lunarcrush', methods=['POST'])
def test_lunarcrush():
    """Test LunarCrush API connection"""
    try:
        config_manager = ConfigManager()
        from src.lunarcrush_client import LunarCrushClient

        client = LunarCrushClient(config_manager.get_all())

        if not client.enabled:
            return jsonify({
                "success": False,
                "error": "LunarCrush library not installed yet. Please rebuild Docker container to install 'lunarcrush' package from requirements.txt"
            }), 400

        # Test by fetching Bitcoin data
        btc_data = client.get_coin_data("BTC-USD")

        if btc_data:
            # Calculate social score
            social_score = client.calculate_social_score(btc_data)

            return jsonify({
                "success": True,
                "message": "LunarCrush API working! ✅",
                "test_coin": "BTC",
                "galaxy_score": btc_data.get("galaxy_score"),
                "alt_rank": btc_data.get("alt_rank"),
                "sentiment": btc_data.get("sentiment"),
                "social_volume": btc_data.get("social_volume"),
                "social_score": social_score.get("total_score"),
                "details": f"Galaxy Score: {btc_data.get('galaxy_score')}/100, AltRank: #{btc_data.get('alt_rank')}, Sentiment: {btc_data.get('sentiment'):.2f}/5"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not fetch data from LunarCrush. API may be down or rate limited."
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test/coingecko', methods=['POST'])
def test_coingecko():
    """Test CoinGecko API connection"""
    try:
        config_manager = ConfigManager()
        from src.coingecko_client import CoinGeckoClient

        client = CoinGeckoClient(config_manager.get_all())

        if not client.enabled:
            return jsonify({
                "success": False,
                "error": "CoinGecko is disabled in configuration"
            }), 400

        # Test by fetching trending coins
        trending = client.get_trending_coins()

        if trending:
            trending_list = [f"{coin['symbol'].upper()}" for coin in trending[:5]]

            return jsonify({
                "success": True,
                "message": "CoinGecko API working! ✅",
                "trending_count": len(trending),
                "top_5_trending": trending_list,
                "details": f"Found {len(trending)} trending coins. Top 5: {', '.join(trending_list)}"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not fetch trending coins from CoinGecko. API may be rate limited."
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/test/news-sentiment', methods=['POST'])
def test_news_sentiment():
    """Test News Sentiment (Crypto Panic) API connection"""
    try:
        config_manager = ConfigManager()
        config = config_manager.get_all()

        if not config.get("news_sentiment_enabled", False):
            return jsonify({
                "success": False,
                "error": "News Sentiment is disabled in configuration. Enable it first to test."
            }), 400

        from src.news_sentiment import NewsSentimentAnalyzer

        analyzer = NewsSentimentAnalyzer(config)

        if not analyzer.enabled:
            return jsonify({
                "success": False,
                "error": "News Sentiment analyzer is not enabled or initialized"
            }), 400

        # Test by getting BTC sentiment
        sentiment = analyzer.get_sentiment("BTC-USD")

        if sentiment:
            return jsonify({
                "success": True,
                "message": "News Sentiment API working! ✅",
                "test_coin": "BTC",
                "sentiment_score": sentiment.get("sentiment_score"),
                "news_count": sentiment.get("news_count"),
                "trending": sentiment.get("trending", False),
                "top_headline": sentiment.get("top_headlines", ["N/A"])[0] if sentiment.get("top_headlines") else "N/A",
                "details": f"Score: {sentiment.get('sentiment_score')}, News: {sentiment.get('news_count')}, Trending: {sentiment.get('trending', False)}"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Could not fetch news sentiment. API may be rate limited (429 errors common on free tier)."
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/debug/reset-account', methods=['POST'])
def reset_account():
    """Reset account for testing - delete all positions and trades"""
    try:
        deleted_files = []

        # Delete positions file
        positions_file = "data/positions.json"
        if os.path.exists(positions_file):
            os.remove(positions_file)
            deleted_files.append(positions_file)

        # Delete trades file
        trades_file = "logs/trades.csv"
        if os.path.exists(trades_file):
            os.remove(trades_file)
            deleted_files.append(trades_file)

        # Reset bot state if running
        if bot:
            # Clear all positions
            bot.risk_manager.positions.clear()

            # Reset capital to initial
            bot.risk_manager.current_capital = bot.config.get("initial_capital", 600.0)
            bot.risk_manager.initial_capital = bot.risk_manager.current_capital

            # Reset daily metrics
            bot.risk_manager.daily_pnl = 0.0
            bot.risk_manager.daily_trades = 0
            bot.risk_manager.total_drawdown = 0.0

            # Save empty positions file
            bot.risk_manager._save_positions()

            # Recreate empty trades CSV
            bot.performance_tracker._initialize_trade_log()

        return jsonify({
            "success": True,
            "message": "Account reset successfully! All positions and trades deleted.",
            "deleted_files": deleted_files
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/debug/reset-config', methods=['POST'])
def reset_configuration():
    """Reset configuration to defaults - backs up current config first"""
    try:
        import shutil
        from datetime import datetime

        config_file = "data/config.json"
        backup_file = f"data/config.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Backup existing config if it exists
        if os.path.exists(config_file):
            shutil.copy2(config_file, backup_file)

        # Reset bot config to defaults
        if bot:
            bot.config_manager.reset_to_defaults()
            bot.config_manager.save()
            bot.config = bot.config_manager.get_all()

            # Reinitialize components that depend on config
            bot.screener.config = bot.config

            return jsonify({
                "success": True,
                "message": "Configuration reset to defaults! Backup saved.",
                "backup_file": backup_file if os.path.exists(config_file) else None,
                "coin_count": len(bot.config.get("screener_coins", [])),
                "coins": bot.config.get("screener_coins", [])[:10]  # Show first 10
            })
        else:
            return jsonify({"success": False, "error": "Bot not initialized"}), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/logs/bot')
def get_bot_logs():
    """Get bot logs (last 2 days)"""
    try:
        from datetime import datetime, timedelta
        log_file = "logs/bot.log"

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()

            # Filter for last 2 days
            cutoff_time = datetime.now(EASTERN) - timedelta(days=2)
            filtered_lines = []

            for line in lines:
                # Try to parse timestamp from line (format: YYYY-MM-DD HH:MM:SS EST)
                try:
                    if len(line) > 19:
                        timestamp_str = line[:19]  # Extract "YYYY-MM-DD HH:MM:SS"
                        log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        log_time = EASTERN.localize(log_time)

                        if log_time >= cutoff_time:
                            filtered_lines.append(line)
                except:
                    # If timestamp parsing fails, include the line anyway
                    filtered_lines.append(line)

            # Reverse so newest is first
            filtered_lines.reverse()

            return jsonify({"logs": filtered_lines})
        else:
            return jsonify({"logs": []})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/logs/claude')
def get_claude_logs():
    """Get Claude analysis logs"""
    try:
        log_file = "logs/claude_analysis.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                content = f.read()
                return jsonify({"logs": content})
        else:
            return jsonify({"logs": "No Claude analysis logs available"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/debug/export-all', methods=['GET'])
def export_all_data():
    """Export all system data for analysis"""
    try:
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "version": __version__,
            "system_info": {
                "timezone": "US/Eastern",
                "current_time": datetime.now(EASTERN).strftime('%Y-%m-%d %H:%M:%S %Z')
            }
        }

        # 1. Configuration Settings
        try:
            config_file = "data/config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    export_data["configuration"] = json.load(f)
            else:
                export_data["configuration"] = {"error": "No config file found"}
        except Exception as e:
            export_data["configuration"] = {"error": str(e)}

        # 2. Open Positions
        try:
            positions_file = "data/positions.json"
            if os.path.exists(positions_file):
                with open(positions_file, 'r') as f:
                    positions_data = json.load(f)
                    export_data["positions"] = positions_data
            else:
                export_data["positions"] = {"_metadata": {}, "positions": {}}
        except Exception as e:
            export_data["positions"] = {"error": str(e)}

        # 3. All Trades (from CSV)
        try:
            if bot and hasattr(bot, 'performance_tracker'):
                trades = bot.performance_tracker.get_all_trades()
                export_data["trades"] = trades
                export_data["trade_count"] = len(trades)
            else:
                export_data["trades"] = []
                export_data["trade_count"] = 0
        except Exception as e:
            export_data["trades"] = {"error": str(e)}

        # 4. Performance Metrics
        try:
            if bot and hasattr(bot, 'performance_tracker'):
                metrics = bot.performance_tracker.calculate_metrics()
                export_data["performance_metrics"] = metrics
            else:
                export_data["performance_metrics"] = {"error": "Bot not running"}
        except Exception as e:
            export_data["performance_metrics"] = {"error": str(e)}

        # 5. Current Balance/Capital State
        try:
            if bot and hasattr(bot, 'risk_manager'):
                export_data["capital_state"] = {
                    "current_capital": bot.risk_manager.current_capital,
                    "initial_capital": bot.risk_manager.initial_capital,
                    "daily_pnl": bot.risk_manager.daily_pnl,
                    "daily_trades": bot.risk_manager.daily_trades,
                    "total_drawdown": bot.risk_manager.total_drawdown,
                    "open_positions_count": len(bot.risk_manager.positions)
                }
            else:
                export_data["capital_state"] = {"error": "Bot not running"}
        except Exception as e:
            export_data["capital_state"] = {"error": str(e)}

        # 6. Screener Configuration
        try:
            if bot and hasattr(bot, 'screener'):
                screener_config = {}
                if hasattr(bot.screener, 'mode'):
                    screener_config["mode"] = bot.screener.mode
                if hasattr(bot.screener, 'get_monitored_coins'):
                    coins = bot.screener.get_monitored_coins()
                    screener_config["monitored_coins"] = coins
                    screener_config["coin_count"] = len(coins)
                # Fallback to config if screener doesn't have these methods
                if not screener_config and bot.config:
                    screener_config["mode"] = bot.config.get("screener_mode", "unknown")
                    screener_config["monitored_coins"] = bot.config.get("screener_coins", [])
                    screener_config["coin_count"] = len(bot.config.get("screener_coins", []))
                export_data["screener_config"] = screener_config
            else:
                export_data["screener_config"] = {"error": "Bot not running or screener not available"}
        except Exception as e:
            export_data["screener_config"] = {"error": str(e)}

        # 7. Recent Screener Results (if available)
        try:
            screener_cache_file = "data/screener_cache.json"
            if os.path.exists(screener_cache_file):
                with open(screener_cache_file, 'r') as f:
                    export_data["screener_results"] = json.load(f)
            else:
                export_data["screener_results"] = {"note": "No cached screener results"}
        except Exception as e:
            export_data["screener_results"] = {"error": str(e)}

        # 8. Claude Analysis History (recent logs)
        try:
            claude_log_file = "logs/claude_analysis.log"
            if os.path.exists(claude_log_file):
                with open(claude_log_file, 'r') as f:
                    content = f.read()
                    # Get last 50 lines or 5000 characters, whichever is smaller
                    lines = content.split('\n')
                    recent_lines = lines[-50:] if len(lines) > 50 else lines
                    export_data["claude_analysis_log"] = '\n'.join(recent_lines)
            else:
                export_data["claude_analysis_log"] = "No Claude analysis logs available"
        except Exception as e:
            export_data["claude_analysis_log"] = {"error": str(e)}

        # 9. Bot Logs (recent)
        try:
            # Try multiple possible log file locations
            possible_log_files = [
                "logs/cryptobot.log",
                "logs/bot.log",
                bot.config.get("log_file") if bot and bot.config else None
            ]

            bot_log_content = None
            for log_file in possible_log_files:
                if log_file and os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        content = f.read()
                        lines = content.split('\n')
                        recent_lines = lines[-100:] if len(lines) > 100 else lines
                        bot_log_content = '\n'.join(recent_lines)
                    break

            if bot_log_content:
                export_data["bot_logs"] = bot_log_content
            else:
                export_data["bot_logs"] = f"No bot logs found. Checked: {', '.join([f for f in possible_log_files if f])}"
        except Exception as e:
            export_data["bot_logs"] = {"error": str(e)}

        # 10. Bot Status
        try:
            export_data["bot_status"] = {
                "running": bot is not None and bot.running if bot else False,
                "dry_run": bot.config.get("dry_run") if bot else None,
                "mode": "DRY RUN" if (bot and bot.config.get("dry_run")) else "LIVE"
            }
        except Exception as e:
            export_data["bot_status"] = {"error": str(e)}

        return jsonify(export_data)

    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


def main():
    """Run Flask server"""
    global bot, bot_thread

    # Configure Flask/Werkzeug logger to use Eastern timezone
    werkzeug_logger = logging.getLogger('werkzeug')
    for handler in werkzeug_logger.handlers:
        handler.setFormatter(EasternFormatter('[%(asctime)s] %(levelname)s: %(message)s'))

    print("=" * 80)
    print(f"CryptoBot Web Dashboard v{__version__} Starting...")
    print(f"Timezone: US/Eastern ({datetime.now(EASTERN).strftime('%Y-%m-%d %H:%M:%S %Z')})")
    print("=" * 80)
    print("Dashboard will be available at http://localhost:8779")
    print("=" * 80)

    # Auto-start the bot
    try:
        bot = TradingBot()
        bot_thread = threading.Thread(target=bot.start)
        bot_thread.daemon = True
        bot_thread.start()
        print("✓ Trading bot auto-started")
    except Exception as e:
        print(f"✗ Failed to auto-start bot: {e}")

    print("=" * 80)

    socketio.run(app, host='0.0.0.0', port=8779, debug=False, allow_unsafe_werkzeug=True)


@app.route('/api/tradingview/webhook', methods=['POST'])
def tradingview_webhook():
    """
    Receive TradingView webhook alerts and execute trades

    Expected JSON payload:
    {
        "secret": "your_webhook_secret",
        "action": "buy" or "sell",
        "symbol": "BTC-USD",
        "price": 50000.00,
        "size_usd": 150.00 (optional),
        "message": "Signal details" (optional)
    }
    """
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        # Verify webhook is enabled
        if not bot.config.get("tradingview_webhook_enabled", False):
            return jsonify({"success": False, "error": "TradingView webhooks are disabled"}), 403

        # Get request data
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No JSON data received"}), 400

        # Verify secret
        webhook_secret = bot.config.get("tradingview_webhook_secret", "")
        if not webhook_secret:
            return jsonify({"success": False, "error": "Webhook secret not configured"}), 403

        provided_secret = data.get("secret", "")
        if provided_secret != webhook_secret:
            logging.warning(f"TradingView webhook authentication failed from {request.remote_addr}")
            return jsonify({"success": False, "error": "Invalid webhook secret"}), 401

        # Extract signal data
        action = data.get("action", "").lower()
        symbol = data.get("symbol", "")
        price = data.get("price")
        size_usd = data.get("size_usd")
        message = data.get("message", "")

        # Validate required fields
        if not action or not symbol:
            return jsonify({"success": False, "error": "Missing required fields: action, symbol"}), 400

        if action not in ["buy", "sell"]:
            return jsonify({"success": False, "error": "Action must be 'buy' or 'sell'"}), 400

        # Log received signal
        logging.info(f"TradingView webhook: {action} {symbol} @ {price} - {message}")

        # Check if auto-trade is enabled
        auto_trade = bot.config.get("tradingview_auto_trade", False)
        if not auto_trade:
            # Log signal but don't execute
            logging.info("TradingView signal received but auto-trade is disabled")
            return jsonify({
                "success": True,
                "message": "Signal received but auto-trade is disabled",
                "action": action,
                "symbol": symbol,
                "executed": False
            })

        # Optional: Require confirmation with technical indicators
        if bot.config.get("tradingview_require_confirmation", True):
            # Get current market data
            df = bot.data_collector.get_historical_candles(symbol, granularity="ONE_HOUR", days=7)
            if df is not None and not df.empty:
                df = bot.signal_generator.generate_all_indicators(df)

                # Check if indicators confirm the signal
                latest = df.iloc[-1]
                rsi = latest.get('rsi_14')
                macd = latest.get('macd')
                macd_signal = latest.get('macd_signal')

                if action == "buy":
                    # Buy confirmation: RSI not overbought, MACD bullish
                    if rsi and rsi > 70:
                        return jsonify({
                            "success": False,
                            "message": "Buy signal rejected: RSI overbought",
                            "rsi": rsi,
                            "executed": False
                        })
                    if macd and macd_signal and macd < macd_signal:
                        return jsonify({
                            "success": False,
                            "message": "Buy signal rejected: MACD bearish",
                            "executed": False
                        })
                elif action == "sell":
                    # Sell confirmation: RSI not oversold
                    if rsi and rsi < 30:
                        return jsonify({
                            "success": False,
                            "message": "Sell signal rejected: RSI oversold",
                            "rsi": rsi,
                            "executed": False
                        })

        # Execute the trade
        if action == "buy":
            # Get current price
            current_price = bot.data_collector.get_current_price(symbol)
            if not current_price:
                return jsonify({"success": False, "error": "Could not get current price"}), 400

            # Use provided size or default to min trade size
            trade_size = size_usd if size_usd else bot.config.get("min_trade_usd", 150.0)

            # Calculate quantity
            quantity = trade_size / current_price

            # Open position
            success, msg, details = bot._open_position(
                symbol,
                quantity,
                current_price,
                f"TradingView: {message}" if message else "TradingView signal"
            )

            return jsonify({
                "success": success,
                "message": msg,
                "details": details,
                "action": "buy",
                "symbol": symbol,
                "price": current_price,
                "quantity": quantity,
                "executed": success
            })

        elif action == "sell":
            # Close position if we have one
            positions = bot.risk_manager.get_all_positions()
            position = next((p for p in positions if p['product_id'] == symbol), None)

            if not position:
                return jsonify({
                    "success": False,
                    "message": f"No open position for {symbol}",
                    "executed": False
                })

            # Close the position
            current_price = bot.data_collector.get_current_price(symbol)
            if not current_price:
                return jsonify({"success": False, "error": "Could not get current price"}), 400

            success, msg, details = bot._close_position(
                symbol,
                current_price,
                f"TradingView: {message}" if message else "TradingView signal"
            )

            return jsonify({
                "success": success,
                "message": msg,
                "details": details,
                "action": "sell",
                "symbol": symbol,
                "price": current_price,
                "executed": success
            })

    except Exception as e:
        import traceback
        logging.error(f"TradingView webhook error: {e}")
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/charts/position-history/<product_id>', methods=['GET'])
def get_position_history(product_id):
    """Get 7-day price history for an open position"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        from datetime import datetime, timedelta

        # Get position info
        positions = bot.risk_manager.get_all_positions()
        position = next((p for p in positions if p['product_id'] == product_id), None)

        if not position:
            return jsonify({"success": False, "error": "Position not found"}), 404

        # Get 7 days of price data (hourly)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        # Use Coinbase data collector to get historical prices
        price_history = bot.data_collector.get_historical_prices(product_id, start_time, end_time)

        # Format response
        response_data = {
            "success": True,
            "product_id": product_id,
            "entry_price": position['entry_price'],
            "entry_timestamp": position['timestamp'],
            "current_quantity": position['quantity'],
            "price_history": price_history
        }

        return jsonify(response_data)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/charts/screener-momentum', methods=['GET'])
def get_screener_momentum():
    """Get momentum data for top 10 screener results"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        from datetime import datetime, timedelta

        # Get latest screener results from localStorage (frontend will send this)
        # For now, run screener to get current top 10
        screener_results = bot.screener.screen_coins()

        # Get top 10 by score
        top_10 = sorted(screener_results, key=lambda x: x.get('score', 0), reverse=True)[:10]

        # Get 24h price history for each
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        momentum_data = []
        for result in top_10:
            product_id = result['product_id']
            try:
                price_history = bot.data_collector.get_historical_prices(product_id, start_time, end_time)
                momentum_data.append({
                    "product_id": product_id,
                    "signal": result.get('signal', 'UNKNOWN'),
                    "score": result.get('score', 0),
                    "price_change_24h": result.get('price_change_24h', 0),
                    "price_history": price_history
                })
            except Exception as e:
                logging.error(f"Error getting price history for {product_id}: {e}")
                continue

        return jsonify({
            "success": True,
            "coins": momentum_data,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/charts/market-regime', methods=['GET'])
def get_market_regime_history():
    """Get market regime analysis history from Claude"""
    try:
        # Read from localStorage (will be sent from frontend)
        # Return the history in chart-friendly format
        history = []

        # Try to read from Claude analysis log
        log_file = "logs/claude_analysis.log"
        if os.path.exists(log_file):
            # Parse last 10 analyses from log
            # This is a simplified version - frontend will use localStorage
            pass

        return jsonify({
            "success": True,
            "message": "Use localStorage claudeAnalysisHistory on frontend",
            "history": history
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    main()
