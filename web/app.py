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

        # Add AUTO mode information to active_config
        if 'active_config' in status:
            config_manager = ConfigManager()
            full_config = config_manager.get_all()

            claude_prompt_strategy = full_config.get('claude_prompt_strategy', 'auto')

            # Get the ACTUAL active screener mode, not the configured mode
            # active_screener_mode is what's actually running (e.g., "mean_reversion")
            # screener_mode might be "auto"
            actual_screener_mode = status['active_config'].get('active_screener_mode', 'auto')
            configured_screener_mode = status['active_config'].get('screener_mode', 'auto')

            # Map screener to prompt (from claude_analyst.py logic)
            screener_to_prompt_mapping = {
                'breakouts': 'breakout_hunter',
                'momentum': 'momentum_bull',
                'trending': 'momentum_bull',
                'oversold': 'dip_buying',
                'bear_bounce': 'bear_survival',
                'mean_reversion': 'bear_survival',
                'scalping': 'range_scalping',
                'range_trading': 'range_scalping',
                'support': 'range_scalping',
                'auto': 'momentum_bull',
                'pending': 'momentum_bull'
            }

            # Determine actual Claude prompt being used
            if claude_prompt_strategy == 'auto':
                # Use the actual active screener mode for mapping
                actual_claude_prompt = screener_to_prompt_mapping.get(actual_screener_mode, 'momentum_bull')
                status['active_config']['auto_mode_active'] = True
                status['active_config']['auto_mode_screener'] = actual_screener_mode
                status['active_config']['auto_mode_claude_prompt'] = actual_claude_prompt
            else:
                status['active_config']['auto_mode_active'] = False
                status['active_config']['auto_mode_screener'] = actual_screener_mode
                status['active_config']['auto_mode_claude_prompt'] = claude_prompt_strategy

        return jsonify(status)
    else:
        return jsonify({"running": False, "error": "Bot not initialized", "version": __version__})


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config_manager = ConfigManager()
    config = config_manager.get_all()

    # Add AUTO mode mapping information
    claude_prompt_strategy = config.get('claude_prompt_strategy', 'auto')
    screener_mode = config.get('screener_mode', 'auto')

    # Map screener to prompt (from claude_analyst.py logic)
    screener_to_prompt_mapping = {
        'breakouts': 'breakout_hunter',
        'momentum': 'momentum_bull',
        'trending': 'momentum_bull',
        'oversold': 'dip_buying',
        'bear_bounce': 'bear_survival',
        'mean_reversion': 'bear_survival',
        'scalping': 'range_scalping',
        'range_trading': 'range_scalping',
        'support': 'range_scalping',
        'auto': 'momentum_bull'
    }

    # Determine actual Claude prompt being used
    if claude_prompt_strategy == 'auto':
        actual_claude_prompt = screener_to_prompt_mapping.get(screener_mode, 'momentum_bull')
        config['auto_mode_active'] = True
        config['auto_mode_screener'] = screener_mode
        config['auto_mode_claude_prompt'] = actual_claude_prompt
    else:
        config['auto_mode_active'] = False
        config['auto_mode_screener'] = screener_mode
        config['auto_mode_claude_prompt'] = claude_prompt_strategy

    return jsonify(config)


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


@app.route('/api/test/coingecko', methods=['POST'])
def test_coingecko():
    """Test CoinGecko API connection"""
    try:
        config_manager = ConfigManager()
        from src.coingecko_data import CoinGeckoCollector

        client = CoinGeckoCollector(config_manager.get_all())

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

        from src.news_sentiment import NewsSentiment

        analyzer = NewsSentiment(config)

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


@app.route('/api/debug/intelligence-export', methods=['POST'])
def intelligence_export():
    """
    Comprehensive intelligence export for AI analysis
    Returns complete snapshot of bot state, decisions, and results
    """
    try:
        data = request.get_json() or {}
        time_range_hours = int(data.get('time_range', 24))
        output_format = data.get('format', 'json')  # 'json' or 'markdown'

        from datetime import timedelta

        # Calculate cutoff time
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)

        intelligence_data = {
            "meta": {
                "export_timestamp": datetime.now(EASTERN).strftime('%Y-%m-%d %H:%M:%S %Z'),
                "bot_version": __version__,
                "time_range_hours": time_range_hours,
                "time_range_start": cutoff_time.strftime('%Y-%m-%d %H:%M:%S'),
                "timezone": "US/Eastern"
            }
        }

        # === 1. CURRENT CONFIGURATION & STRATEGY ===
        try:
            config_file = "data/config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    intelligence_data["configuration"] = {
                        "trading_parameters": {
                            "initial_capital": config.get("initial_capital"),
                            "max_positions": config.get("max_positions"),
                            "position_size_pct": config.get("position_size_pct"),
                            "stop_loss_pct": config.get("stop_loss_pct"),
                            "take_profit_pct": config.get("take_profit_pct"),
                            "max_daily_loss_pct": config.get("max_daily_loss_pct"),
                            "max_drawdown_pct": config.get("max_drawdown_pct"),
                            "trailing_stop_enabled": config.get("trailing_stop_enabled"),
                            "trailing_stop_activation_pct": config.get("trailing_stop_activation_pct"),
                            "trailing_stop_distance_pct": config.get("trailing_stop_distance_pct")
                        },
                        "screener_settings": {
                            "mode": config.get("screener_mode"),
                            "max_results": config.get("screener_max_results"),
                            "monitored_coins": config.get("screener_coins", []),
                            "coin_count": len(config.get("screener_coins", []))
                        },
                        "claude_ai_settings": {
                            "enabled": config.get("claude_enabled"),
                            "analysis_mode": config.get("claude_analysis_mode"),
                            "prompt_strategy": config.get("claude_prompt_strategy"),
                            "confidence_threshold": config.get("claude_confidence_threshold"),
                            "risk_tolerance": config.get("claude_risk_tolerance"),
                            "analysis_schedule": config.get("claude_analysis_schedule"),
                            "max_trade_suggestions": config.get("claude_max_trade_suggestions")
                        },
                        "data_sources": {
                            "news_sentiment_enabled": config.get("news_sentiment_enabled"),
                            "coingecko_enabled": config.get("coingecko_enabled")
                        },
                        "mode": "DRY_RUN" if config.get("dry_run") else "LIVE_TRADING"
                    }
        except Exception as e:
            intelligence_data["configuration"] = {"error": str(e)}

        # === 2. CURRENT PORTFOLIO STATE ===
        try:
            if bot and hasattr(bot, 'risk_manager'):
                rm = bot.risk_manager
                intelligence_data["portfolio_state"] = {
                    "current_capital": rm.current_capital,
                    "initial_capital": rm.initial_capital,
                    "total_pnl": rm.current_capital - rm.initial_capital,
                    "total_pnl_pct": ((rm.current_capital - rm.initial_capital) / rm.initial_capital * 100) if rm.initial_capital > 0 else 0,
                    "daily_pnl": rm.daily_pnl,
                    "daily_trades": rm.daily_trades,
                    "total_drawdown": rm.total_drawdown,
                    "open_positions_count": len(rm.positions),
                    "open_positions": [
                        {
                            "product_id": pos["product_id"],
                            "quantity": pos["quantity"],
                            "entry_price": pos["entry_price"],
                            "current_price": pos.get("current_price"),
                            "unrealized_pnl": pos.get("unrealized_pnl"),
                            "unrealized_pnl_pct": pos.get("unrealized_pnl_pct"),
                            "entry_time": pos.get("entry_time"),
                            "stop_loss": pos.get("stop_loss"),
                            "take_profit": pos.get("take_profit")
                        }
                        for pos in rm.get_all_positions()
                    ]
                }
            else:
                intelligence_data["portfolio_state"] = {"error": "Bot not running"}
        except Exception as e:
            intelligence_data["portfolio_state"] = {"error": str(e)}

        # === 3. TRADE HISTORY (filtered by time range) ===
        try:
            if bot and hasattr(bot, 'performance_tracker'):
                all_trades = bot.performance_tracker.get_all_trades()
                recent_trades = [
                    trade for trade in all_trades
                    if datetime.fromisoformat(trade.get("entry_time", "1970-01-01")) >= cutoff_time
                ]
                intelligence_data["trade_history"] = {
                    "total_trades_in_range": len(recent_trades),
                    "trades": recent_trades
                }
            else:
                intelligence_data["trade_history"] = {"error": "Bot not running"}
        except Exception as e:
            intelligence_data["trade_history"] = {"error": str(e)}

        # === 4. PERFORMANCE METRICS ===
        try:
            if bot and hasattr(bot, 'performance_tracker'):
                metrics = bot.performance_tracker.calculate_metrics()
                intelligence_data["performance_metrics"] = metrics
            else:
                intelligence_data["performance_metrics"] = {"error": "Bot not running"}
        except Exception as e:
            intelligence_data["performance_metrics"] = {"error": str(e)}

        # === 5. SCREENER RESULTS & DECISIONS ===
        try:
            # Get latest screener results
            screener_file = "data/latest_screener.json"
            if os.path.exists(screener_file):
                with open(screener_file, 'r') as f:
                    screener_data = json.load(f)
                    intelligence_data["screener_results"] = {
                        "timestamp": screener_data.get("timestamp"),
                        "active_mode": screener_data.get("mode"),
                        "opportunity_count": len(screener_data.get("opportunities", [])),
                        "opportunities": screener_data.get("opportunities", [])
                    }
            else:
                intelligence_data["screener_results"] = {"note": "No recent screener results"}
        except Exception as e:
            intelligence_data["screener_results"] = {"error": str(e)}

        # === 6. CLAUDE AI ANALYSIS & RECOMMENDATIONS ===
        try:
            # Get latest Claude analysis
            claude_file = "data/latest_claude_analysis.json"
            if os.path.exists(claude_file):
                with open(claude_file, 'r') as f:
                    claude_data = json.load(f)
                    analysis = claude_data.get("analysis", {})
                    intelligence_data["claude_analysis"] = {
                        "timestamp": claude_data.get("timestamp"),
                        "market_assessment": analysis.get("market_assessment"),
                        "recommended_actions": analysis.get("recommended_actions", []),
                        "risk_warnings": analysis.get("risk_warnings", []),
                        "config_suggestions": analysis.get("config_suggestions", [])
                    }
            else:
                intelligence_data["claude_analysis"] = {"note": "No recent Claude analysis"}

            # Get Claude analysis logs (recent)
            claude_log = "logs/claude_analysis.log"
            if os.path.exists(claude_log):
                with open(claude_log, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    recent_lines = lines[-100:]
                    intelligence_data["claude_analysis_log"] = '\n'.join(recent_lines)
        except Exception as e:
            intelligence_data["claude_analysis"] = {"error": str(e)}

        # === 7. MARKET CONTEXT ===
        try:
            if bot:
                # Get current market data
                market_context = {}

                # Fear & Greed Index
                if hasattr(bot, 'data_collector'):
                    fg = bot.data_collector.get_fear_greed_index()
                    market_context["fear_greed_index"] = fg

                    # BTC price and changes
                    btc_changes = bot.data_collector.get_price_changes("BTC-USD")
                    market_context["btc_data"] = btc_changes

                # Trending coins
                if hasattr(bot, 'coingecko') and bot.config.get("coingecko_enabled"):
                    trending = bot.coingecko.get_trending_coins()
                    market_context["trending_coins"] = trending[:10] if trending else []

                intelligence_data["market_context"] = market_context
            else:
                intelligence_data["market_context"] = {"error": "Bot not running"}
        except Exception as e:
            intelligence_data["market_context"] = {"error": str(e)}

        # === 8. REJECTED OPPORTUNITIES (Why didn't we trade?) ===
        try:
            # Parse bot logs for rejected opportunities
            bot_log_file = "logs/cryptobot.log"
            if os.path.exists(bot_log_file):
                with open(bot_log_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')

                    # Look for rejection reasons in recent logs
                    rejection_keywords = ["rejected", "skipped", "blocked", "failed", "insufficient"]
                    rejections = []
                    for line in lines[-500:]:  # Last 500 lines
                        if any(keyword in line.lower() for keyword in rejection_keywords):
                            rejections.append(line)

                    intelligence_data["rejected_opportunities"] = {
                        "count": len(rejections),
                        "reasons": rejections[-50:]  # Last 50 rejections
                    }
        except Exception as e:
            intelligence_data["rejected_opportunities"] = {"error": str(e)}

        # === 9. BOT DECISION LOG (Recent actions) ===
        try:
            bot_log_file = "logs/cryptobot.log"
            if os.path.exists(bot_log_file):
                with open(bot_log_file, 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    intelligence_data["bot_decision_log"] = '\n'.join(lines[-200:])
        except Exception as e:
            intelligence_data["bot_decision_log"] = {"error": str(e)}

        # === Convert to Markdown if requested ===
        if output_format == 'markdown':
            markdown_content = _convert_to_markdown(intelligence_data)
            return jsonify({"format": "markdown", "content": markdown_content})
        else:
            return jsonify({"format": "json", "content": intelligence_data})

    except Exception as e:
        return jsonify({"error": f"Intelligence export failed: {str(e)}"}), 500


def _convert_to_markdown(data: dict) -> str:
    """Convert intelligence data to markdown format"""
    md = []

    md.append("# 🧠 CryptoBot Intelligence Export\n")
    md.append(f"**Generated:** {data['meta']['export_timestamp']}")
    md.append(f"**Bot Version:** {data['meta']['bot_version']}")
    md.append(f"**Time Range:** Last {data['meta']['time_range_hours']} hours")
    md.append(f"**Analysis Period:** {data['meta']['time_range_start']} to present\n")
    md.append("---\n")

    # Configuration
    if "configuration" in data:
        md.append("## 📋 Current Configuration & Strategy\n")
        config = data["configuration"]

        if "trading_parameters" in config:
            md.append("### Trading Parameters")
            tp = config["trading_parameters"]
            md.append(f"- **Initial Capital:** ${tp.get('initial_capital', 0):,.2f}")
            md.append(f"- **Max Positions:** {tp.get('max_positions')}")
            md.append(f"- **Position Size:** {tp.get('position_size_pct', 0)*100:.1f}%")
            md.append(f"- **Stop Loss:** {tp.get('stop_loss_pct', 0)*100:.1f}%")
            md.append(f"- **Take Profit:** {tp.get('take_profit_pct', 0)*100:.1f}%")
            md.append(f"- **Max Daily Loss:** {tp.get('max_daily_loss_pct', 0)*100:.1f}%")
            md.append(f"- **Max Drawdown:** {tp.get('max_drawdown_pct', 0)*100:.1f}%")
            md.append(f"- **Trailing Stop:** {'Enabled' if tp.get('trailing_stop_enabled') else 'Disabled'}\n")

        if "screener_settings" in config:
            md.append("### Screener Settings")
            ss = config["screener_settings"]
            md.append(f"- **Mode:** {ss.get('mode')}")
            md.append(f"- **Max Results:** {ss.get('max_results')}")
            md.append(f"- **Monitored Coins:** {ss.get('coin_count')} coins\n")

        if "claude_ai_settings" in config:
            md.append("### Claude AI Settings")
            cs = config["claude_ai_settings"]
            md.append(f"- **Enabled:** {cs.get('enabled')}")
            md.append(f"- **Mode:** {cs.get('analysis_mode')}")
            md.append(f"- **Prompt Strategy:** {cs.get('prompt_strategy')}")
            md.append(f"- **Confidence Threshold:** {cs.get('confidence_threshold')}%")
            md.append(f"- **Risk Tolerance:** {cs.get('risk_tolerance')}")
            md.append(f"- **Schedule:** {cs.get('analysis_schedule')}\n")

    # Portfolio State
    if "portfolio_state" in data and "error" not in data["portfolio_state"]:
        md.append("## 💰 Current Portfolio State\n")
        ps = data["portfolio_state"]
        md.append(f"- **Current Capital:** ${ps.get('current_capital', 0):,.2f}")
        md.append(f"- **Initial Capital:** ${ps.get('initial_capital', 0):,.2f}")
        md.append(f"- **Total P&L:** ${ps.get('total_pnl', 0):+,.2f} ({ps.get('total_pnl_pct', 0):+.2f}%)")
        md.append(f"- **Daily P&L:** ${ps.get('daily_pnl', 0):+,.2f}")
        md.append(f"- **Daily Trades:** {ps.get('daily_trades', 0)}")
        md.append(f"- **Total Drawdown:** {ps.get('total_drawdown', 0):.2f}%")
        md.append(f"- **Open Positions:** {ps.get('open_positions_count', 0)}\n")

        if ps.get('open_positions'):
            md.append("### Open Positions")
            for pos in ps['open_positions']:
                md.append(f"\n**{pos['product_id']}:**")
                md.append(f"- Entry: ${pos['entry_price']:,.2f}")
                md.append(f"- Current: ${pos.get('current_price', 0):,.2f}")
                md.append(f"- P&L: ${pos.get('unrealized_pnl', 0):+,.2f} ({pos.get('unrealized_pnl_pct', 0):+.2f}%)")

    # Trade History
    if "trade_history" in data and "error" not in data["trade_history"]:
        md.append(f"\n## 📊 Trade History ({data['trade_history'].get('total_trades_in_range', 0)} trades)\n")
        trades = data["trade_history"].get("trades", [])
        for i, trade in enumerate(trades[:10], 1):  # Show first 10
            md.append(f"\n### Trade #{i}: {trade.get('product_id')}")
            md.append(f"- **Action:** {trade.get('action')}")
            md.append(f"- **Entry:** ${trade.get('entry_price', 0):,.2f} @ {trade.get('entry_time')}")
            md.append(f"- **Exit:** ${trade.get('exit_price', 0):,.2f} @ {trade.get('exit_time')}")
            md.append(f"- **P&L:** ${trade.get('pnl', 0):+,.2f} ({trade.get('pnl_pct', 0):+.2f}%)")
            md.append(f"- **Reason:** {trade.get('exit_reason', 'N/A')}")

    # Screener Results
    if "screener_results" in data and "error" not in data["screener_results"]:
        md.append(f"\n## 🔍 Latest Screener Results\n")
        sr = data["screener_results"]
        md.append(f"- **Timestamp:** {sr.get('timestamp')}")
        md.append(f"- **Active Mode:** {sr.get('active_mode')}")
        md.append(f"- **Opportunities Found:** {sr.get('opportunity_count')}\n")

        if sr.get('opportunities'):
            md.append("### Top Opportunities")
            for opp in sr['opportunities'][:5]:
                md.append(f"\n**{opp.get('product_id')}:**")
                md.append(f"- Score: {opp.get('score', 0):.1f}")
                md.append(f"- Signal: {opp.get('signal')}")
                md.append(f"- Confidence: {opp.get('confidence', 0)}%")
                md.append(f"- Price: ${opp.get('price', 0):,.2f}")
                md.append(f"- 24h Change: {opp.get('price_change_24h', 0):+.2f}%")

    # Claude Analysis
    if "claude_analysis" in data and "error" not in data["claude_analysis"]:
        md.append("\n## 🤖 Claude AI Analysis\n")
        ca = data["claude_analysis"]
        md.append(f"- **Timestamp:** {ca.get('timestamp')}\n")

        if "market_assessment" in ca and ca["market_assessment"]:
            ma = ca["market_assessment"]
            md.append("### Market Assessment")
            md.append(f"- **Regime:** {ma.get('regime', 'N/A').upper()}")
            md.append(f"- **Confidence:** {ma.get('confidence', 0)}%")
            md.append(f"- **Risk Level:** {ma.get('risk_level', 'N/A').upper()}\n")

            if ma.get('key_factors'):
                md.append("**Key Factors:**")
                for factor in ma['key_factors']:
                    md.append(f"- {factor}")

        if ca.get('recommended_actions'):
            md.append("\n### Recommended Actions")
            for i, rec in enumerate(ca['recommended_actions'], 1):
                md.append(f"\n**Recommendation #{i}:**")
                md.append(f"- **Coin:** {rec.get('coin')}")
                md.append(f"- **Action:** {rec.get('action').upper()}")
                md.append(f"- **Conviction:** {rec.get('conviction', 0)}%")
                md.append(f"- **Entry:** ${rec.get('target_entry', 0):,.2f}")
                md.append(f"- **Stop Loss:** ${rec.get('stop_loss', 0):,.2f}")
                md.append(f"- **Take Profit:** {rec.get('take_profit', [])}")
                md.append(f"- **Reasoning:** {rec.get('reasoning', 'N/A')}")

        if ca.get('risk_warnings'):
            md.append("\n### ⚠️ Risk Warnings")
            for warning in ca['risk_warnings']:
                md.append(f"- {warning}")

    # Market Context
    if "market_context" in data and "error" not in data["market_context"]:
        md.append("\n## 🌍 Market Context\n")
        mc = data["market_context"]

        if "fear_greed_index" in mc and mc["fear_greed_index"]:
            fg = mc["fear_greed_index"]
            md.append(f"- **Fear & Greed Index:** {fg.get('value')} ({fg.get('classification')})")

        if "btc_data" in mc and mc["btc_data"]:
            btc = mc["btc_data"]
            md.append(f"- **BTC Price:** ${btc.get('price', 0):,.2f}")
            md.append(f"- **BTC 24h Change:** {btc.get('price_change_24h', 0):+.2f}%")
            md.append(f"- **BTC 7d Change:** {btc.get('price_change_7d', 0):+.2f}%")

    # Performance Metrics
    if "performance_metrics" in data and "error" not in data["performance_metrics"]:
        md.append("\n## 📈 Performance Metrics\n")
        pm = data["performance_metrics"]
        md.append(f"- **Total Trades:** {pm.get('total_trades', 0)}")
        md.append(f"- **Win Rate:** {pm.get('win_rate', 0):.1f}%")
        md.append(f"- **Average Win:** {pm.get('avg_win', 0):.2f}%")
        md.append(f"- **Average Loss:** {pm.get('avg_loss', 0):.2f}%")
        md.append(f"- **Profit Factor:** {pm.get('profit_factor', 0):.2f}")
        md.append(f"- **Sharpe Ratio:** {pm.get('sharpe_ratio', 0):.2f}")

    md.append("\n---\n")
    md.append("*Generated by CryptoBot Intelligence Export*")

    return '\n'.join(md)


@app.route('/api/debug/health-check', methods=['POST'])
def bot_health_check():
    """
    Automated bot health check - analyzes logic consistency and performance
    Checks last N hours of data for problems, strategy alignment, and trade quality
    """
    try:
        data = request.get_json() or {}
        time_range_hours = int(data.get('time_range', 6))  # Default 6 hours
        include_recommendations = data.get('include_recommendations', True)

        from datetime import timedelta
        import logging
        logger = logging.getLogger("CryptoBot.HealthCheck")

        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)

        health_report = {
            "timestamp": datetime.now(EASTERN).strftime('%Y-%m-%d %H:%M:%S %Z'),
            "time_range_hours": time_range_hours,
            "overall_health": "OK",  # Will be updated to WARNING or CRITICAL
            "issues": [],
            "warnings": [],
            "ok_checks": []
        }

        if include_recommendations:
            health_report["recommendations"] = []

        # === FORCE FRESH DATA COLLECTION FROM BOT ===
        # For remote bots (Pi), we get fresh data from the bot object, not files
        logger.info("Health check: Getting fresh data from bot object...")

        # Get fresh status from bot (includes last run times)
        bot_status = None
        try:
            if bot and hasattr(bot, 'get_status'):
                bot_status = bot.get_status()
                logger.info(f"Got bot status: {bot_status.keys() if bot_status else 'None'}")
        except Exception as e:
            logger.warning(f"Could not get bot status: {e}")

        # Force bot to refresh its Fear & Greed Index
        try:
            if bot and hasattr(bot, 'data_collector'):
                bot.data_collector.get_fear_greed_index(use_cache=False)
        except Exception as e:
            logger.warning(f"Could not refresh Fear & Greed: {e}")

        # Force bot to refresh current prices for all positions
        try:
            if bot and hasattr(bot, 'risk_manager'):
                positions = bot.risk_manager.get_all_positions()
                for pos in positions:
                    if hasattr(bot, 'data_collector'):
                        bot.data_collector.get_current_price(pos['product_id'], use_cache=False)
        except Exception as e:
            logger.warning(f"Could not refresh position prices: {e}")

        # === CHECK 1: Bot Running State ===
        if not bot or not bot.running:
            health_report["issues"].append({
                "severity": "CRITICAL",
                "category": "Bot State",
                "issue": "Bot is not running",
                "impact": "No trading activity possible"
            })
            health_report["overall_health"] = "CRITICAL"
            if include_recommendations:
                health_report["recommendations"].append({
                    "priority": "HIGH",
                    "action": "Start the bot from the Controls tab"
                })
            return jsonify(health_report)

        # === CHECK 2: Configuration Sanity ===
        try:
            config = bot.config

            # Check market regime vs strategy alignment
            fear_greed = bot.data_collector.get_fear_greed_index()
            if fear_greed:
                fg_value = fear_greed.get('value', 50)
                screener_mode = config.get('screener_mode', 'auto')

                # Bear market (FG < 45) checks
                if fg_value < 45:
                    # Should be using mean_reversion/bear_bounce
                    if screener_mode not in ['mean_reversion', 'bear_bounce', 'auto']:
                        health_report["issues"].append({
                            "severity": "CRITICAL",
                            "category": "Strategy Alignment",
                            "issue": f"Bear market (FG={fg_value}) but using {screener_mode} strategy",
                            "impact": "High risk of buying overbought bounces",
                            "current_value": screener_mode,
                            "expected_value": "mean_reversion or bear_bounce"
                        })
                        health_report["overall_health"] = "CRITICAL"
                        if include_recommendations:
                            health_report["recommendations"].append({
                                "priority": "CRITICAL",
                                "action": "Switch screener to 'mean_reversion' or set to 'auto' mode"
                            })

                    # Position size should be conservative
                    pos_size = config.get('position_size_pct', 0.10)
                    if pos_size > 0.12:
                        health_report["warnings"].append({
                            "severity": "WARNING",
                            "category": "Risk Management",
                            "issue": f"Position size {pos_size*100:.0f}% too aggressive for bear market (FG={fg_value})",
                            "impact": "Higher risk per trade in volatile conditions",
                            "current_value": f"{pos_size*100:.0f}%",
                            "recommended_value": "8-10%"
                        })
                        if health_report["overall_health"] == "OK":
                            health_report["overall_health"] = "WARNING"
                        if include_recommendations:
                            health_report["recommendations"].append({
                                "priority": "MEDIUM",
                                "action": "Reduce position_size_pct to 0.08-0.10 (8-10%) for bear market"
                            })

                # Bull market (FG > 55) checks
                elif fg_value > 55:
                    if screener_mode not in ['momentum', 'breakouts', 'trending', 'auto']:
                        health_report["warnings"].append({
                            "severity": "WARNING",
                            "category": "Strategy Alignment",
                            "issue": f"Bull market (FG={fg_value}) but using {screener_mode} strategy",
                            "impact": "Missing momentum opportunities",
                            "current_value": screener_mode,
                            "suggested_value": "momentum or breakouts"
                        })
                        if health_report["overall_health"] == "OK":
                            health_report["overall_health"] = "WARNING"
                        if include_recommendations:
                            health_report["recommendations"].append({
                                "priority": "MEDIUM",
                                "action": "Consider switching to 'momentum' or 'breakouts' strategy"
                            })
                else:
                    health_report["ok_checks"].append({
                        "category": "Strategy Alignment",
                        "check": f"Market regime appropriate (FG={fg_value}, Mode={screener_mode})"
                    })

            # Check if stop loss is reasonable
            stop_loss = config.get('stop_loss_pct', 0.05)
            if stop_loss > 0.10:
                health_report["warnings"].append({
                    "severity": "WARNING",
                    "category": "Risk Management",
                    "issue": f"Stop loss {stop_loss*100:.0f}% is very wide",
                    "impact": "Large potential losses per trade",
                    "current_value": f"{stop_loss*100:.0f}%",
                    "recommended_value": "5-8%"
                })
                if health_report["overall_health"] == "OK":
                    health_report["overall_health"] = "WARNING"
            elif stop_loss < 0.03:
                health_report["warnings"].append({
                    "severity": "WARNING",
                    "category": "Risk Management",
                    "issue": f"Stop loss {stop_loss*100:.0f}% is very tight",
                    "impact": "May get stopped out by normal volatility",
                    "current_value": f"{stop_loss*100:.0f}%",
                    "recommended_value": "5-8%"
                })
                if health_report["overall_health"] == "OK":
                    health_report["overall_health"] = "WARNING"
            else:
                health_report["ok_checks"].append({
                    "category": "Risk Management",
                    "check": f"Stop loss reasonable ({stop_loss*100:.0f}%)"
                })

        except Exception as e:
            logger.error(f"Config check error: {e}")
            health_report["warnings"].append({
                "severity": "WARNING",
                "category": "System",
                "issue": f"Could not validate configuration: {str(e)}"
            })

        # === CHECK 3: Recent Trade Quality ===
        try:
            if hasattr(bot, 'performance_tracker'):
                all_trades = bot.performance_tracker.get_all_trades()
                recent_trades = [
                    t for t in all_trades
                    if datetime.fromisoformat(t.get("entry_time", "1970-01-01")) >= cutoff_time
                ]

                if recent_trades:
                    # Calculate win rate
                    winning_trades = [t for t in recent_trades if t.get('pnl', 0) > 0]
                    win_rate = (len(winning_trades) / len(recent_trades)) * 100

                    if win_rate < 30:
                        health_report["issues"].append({
                            "severity": "CRITICAL",
                            "category": "Trade Quality",
                            "issue": f"Win rate very low: {win_rate:.1f}% ({len(winning_trades)}/{len(recent_trades)} trades)",
                            "impact": "Strategy not working in current market",
                            "current_value": f"{win_rate:.1f}%",
                            "expected_value": ">40%"
                        })
                        health_report["overall_health"] = "CRITICAL"
                        if include_recommendations:
                            health_report["recommendations"].append({
                                "priority": "CRITICAL",
                                "action": "Review strategy alignment, consider switching modes or reducing position size"
                            })
                    elif win_rate < 45:
                        health_report["warnings"].append({
                            "severity": "WARNING",
                            "category": "Trade Quality",
                            "issue": f"Win rate below target: {win_rate:.1f}% ({len(winning_trades)}/{len(recent_trades)} trades)",
                            "impact": "Suboptimal performance",
                            "current_value": f"{win_rate:.1f}%",
                            "target_value": ">45%"
                        })
                        if health_report["overall_health"] == "OK":
                            health_report["overall_health"] = "WARNING"
                    else:
                        health_report["ok_checks"].append({
                            "category": "Trade Quality",
                            "check": f"Win rate healthy: {win_rate:.1f}% ({len(winning_trades)}/{len(recent_trades)} trades)"
                        })

                    # Check average loss size
                    losing_trades = [t for t in recent_trades if t.get('pnl', 0) < 0]
                    if losing_trades:
                        avg_loss_pct = sum(t.get('pnl_pct', 0) for t in losing_trades) / len(losing_trades)
                        if avg_loss_pct < -8:
                            health_report["warnings"].append({
                                "severity": "WARNING",
                                "category": "Risk Management",
                                "issue": f"Average loss {avg_loss_pct:.1f}% exceeds stop loss",
                                "impact": "Stops not being honored or slippage issues",
                                "current_value": f"{avg_loss_pct:.1f}%",
                                "expected_value": f"~{config.get('stop_loss_pct', 0.05)*-100:.0f}%"
                            })
                            if health_report["overall_health"] == "OK":
                                health_report["overall_health"] = "WARNING"
                else:
                    health_report["ok_checks"].append({
                        "category": "Trade Activity",
                        "check": f"No trades in last {time_range_hours} hours (waiting for opportunities)"
                    })
        except Exception as e:
            logger.error(f"Trade quality check error: {e}")
            health_report["warnings"].append({
                "severity": "WARNING",
                "category": "System",
                "issue": f"Could not analyze trade quality: {str(e)}"
            })

        # === CHECK 4: Screener Signal Quality ===
        try:
            # Get screener data from bot status (for remote Pi bot)
            screener_last_run = None
            opportunities = []

            if bot_status and 'screener' in bot_status:
                screener_info = bot_status['screener']
                screener_last_run_str = screener_info.get('last_run')
                opportunities = screener_info.get('top_opportunities', [])

                if screener_last_run_str:
                    try:
                        # Parse "MM/DD/YYYY, HH:MM:SS AM/PM" format from status
                        screener_last_run = datetime.strptime(screener_last_run_str, "%m/%d/%Y, %I:%M:%S %p")
                    except:
                        # Try ISO format as fallback
                        try:
                            screener_last_run = datetime.fromisoformat(screener_last_run_str.replace('EST', '').replace('UTC', '').strip())
                            if screener_last_run.tzinfo is not None:
                                screener_last_run = screener_last_run.replace(tzinfo=None)
                        except Exception as e:
                            logger.warning(f"Could not parse screener timestamp: {screener_last_run_str}, error: {e}")

            if screener_last_run:
                age_minutes = (datetime.now() - screener_last_run).total_seconds() / 60

                # Dynamic threshold based on bot's check interval
                check_interval_sec = config.get('check_interval_sec', 3600)
                check_interval_minutes = check_interval_sec / 60
                # Warn if data is older than 2.5x the check interval (gives buffer for current cycle)
                threshold_minutes = check_interval_minutes * 2.5

                if age_minutes > threshold_minutes:
                    health_report["warnings"].append({
                        "severity": "WARNING",
                        "category": "Data Freshness",
                        "issue": f"Screener last ran {age_minutes/60:.1f} hours ago (>{threshold_minutes/60:.1f} hours)",
                        "impact": "May be waiting for next bot check cycle or bot may be stuck",
                        "current_value": f"{age_minutes/60:.1f} hours ago",
                        "expected_value": f"<{threshold_minutes/60:.1f} hours (check interval: {check_interval_minutes:.0f} min)",
                        "note": f"Bot runs every {check_interval_minutes:.0f} minutes. Data age beyond 2.5x interval suggests bot may be stuck."
                    })
                    if health_report["overall_health"] == "OK":
                        health_report["overall_health"] = "WARNING"
                else:
                    health_report["ok_checks"].append({
                        "category": "Data Freshness",
                        "check": f"Screener ran recently ({age_minutes:.0f} minutes ago, threshold: {threshold_minutes:.0f} min)"
                    })
            else:
                health_report["warnings"].append({
                    "severity": "WARNING",
                    "category": "Data Freshness",
                    "issue": "No screener run time available",
                    "impact": "Cannot determine if screener is running"
                })
                if health_report["overall_health"] == "OK":
                    health_report["overall_health"] = "WARNING"

            # Check signal quality (regardless of timestamp)
            if opportunities:
                strong_sells = [o for o in opportunities if 'sell' in o.get('signal', '').lower()]
                if strong_sells:
                    health_report["warnings"].append({
                        "severity": "WARNING",
                        "category": "Signal Quality",
                        "issue": f"Screener found {len(strong_sells)} SELL signals in top results",
                        "impact": "Limited buy opportunities",
                        "details": [f"{o.get('product_id', 'Unknown')}: {o.get('signal', 'Unknown')}" for o in strong_sells[:3]]
                    })
                    if health_report["overall_health"] == "OK":
                        health_report["overall_health"] = "WARNING"
            elif screener_last_run:  # Only warn if we know screener ran but found nothing
                health_report["warnings"].append({
                    "severity": "WARNING",
                    "category": "Signal Quality",
                    "issue": "Screener found no opportunities",
                    "impact": "No trading signals available"
                })
                if health_report["overall_health"] == "OK":
                    health_report["overall_health"] = "WARNING"
        except Exception as e:
            logger.error(f"Screener check error: {e}")

        # === CHECK 5: Open Positions Risk ===
        try:
            if hasattr(bot, 'risk_manager'):
                positions = bot.risk_manager.get_all_positions()

                if positions:
                    # Check each position for problems
                    for pos in positions:
                        product_id = pos['product_id']
                        entry_price = pos['entry_price']

                        # Get current price
                        current_price = bot.data_collector.get_current_price(product_id)
                        if current_price:
                            pnl_pct = ((current_price - entry_price) / entry_price) * 100

                            # Check if position is deep underwater
                            if pnl_pct < -10:
                                health_report["issues"].append({
                                    "severity": "CRITICAL",
                                    "category": "Open Positions",
                                    "issue": f"{product_id} down {pnl_pct:.1f}% (stop loss should have triggered)",
                                    "impact": "Position should have been closed by stop loss",
                                    "current_pnl": f"{pnl_pct:.1f}%"
                                })
                                health_report["overall_health"] = "CRITICAL"
                                if include_recommendations:
                                    health_report["recommendations"].append({
                                        "priority": "CRITICAL",
                                        "action": f"Manually close {product_id} position - stop loss may have failed"
                                    })

                            # Check if screener now says SELL
                            screener_file = "data/latest_screener.json"
                            if os.path.exists(screener_file):
                                with open(screener_file, 'r') as f:
                                    screener_data = json.load(f)
                                    for opp in screener_data.get('opportunities', []):
                                        if opp.get('product_id') == product_id:
                                            signal = opp.get('signal', '').lower()
                                            if 'sell' in signal:
                                                health_report["warnings"].append({
                                                    "severity": "WARNING",
                                                    "category": "Open Positions",
                                                    "issue": f"{product_id} now has {signal.upper()} signal",
                                                    "impact": "Holding position contradicting current analysis",
                                                    "current_pnl": f"{pnl_pct:.1f}%",
                                                    "signal": signal
                                                })
                                                if health_report["overall_health"] == "OK":
                                                    health_report["overall_health"] = "WARNING"
                                                if include_recommendations:
                                                    health_report["recommendations"].append({
                                                        "priority": "MEDIUM",
                                                        "action": f"Consider closing {product_id} - signals turned bearish"
                                                    })
                else:
                    health_report["ok_checks"].append({
                        "category": "Open Positions",
                        "check": "No open positions (no position risk)"
                    })
        except Exception as e:
            logger.error(f"Position risk check error: {e}")

        # === CHECK 6: Account Health ===
        try:
            if hasattr(bot, 'risk_manager'):
                rm = bot.risk_manager
                initial_capital = rm.initial_capital
                current_cash = rm.current_capital

                # CRITICAL FIX: Calculate total account value including open positions
                positions = rm.get_all_positions()
                total_position_value = 0.0

                if positions:
                    for pos in positions:
                        product_id = pos['product_id']
                        quantity = pos['quantity']

                        # Get current price for this position
                        current_price = bot.data_collector.get_current_price(product_id)
                        if current_price:
                            position_value = quantity * current_price
                            total_position_value += position_value

                # Total account value = cash + position values
                total_account_value = current_cash + total_position_value
                total_drawdown_pct = ((total_account_value - initial_capital) / initial_capital) * 100

                # Build detailed breakdown
                breakdown_text = f"Cash: ${current_cash:.2f}"
                if positions:
                    breakdown_text += f" + Positions: ${total_position_value:.2f} = Total: ${total_account_value:.2f}"
                else:
                    breakdown_text += f" (no open positions)"

                if total_drawdown_pct < -20:
                    health_report["issues"].append({
                        "severity": "CRITICAL",
                        "category": "Account Health",
                        "issue": f"Total account down {abs(total_drawdown_pct):.1f}% from initial capital",
                        "impact": "Significant capital loss",
                        "current_value": breakdown_text,
                        "initial_value": f"${initial_capital:.2f}"
                    })
                    health_report["overall_health"] = "CRITICAL"
                    if include_recommendations:
                        health_report["recommendations"].append({
                            "priority": "CRITICAL",
                            "action": "Consider stopping bot and reviewing strategy - significant losses"
                        })
                elif total_drawdown_pct < -10:
                    health_report["warnings"].append({
                        "severity": "WARNING",
                        "category": "Account Health",
                        "issue": f"Total account down {abs(total_drawdown_pct):.1f}% from initial capital",
                        "impact": "Notable capital loss",
                        "current_value": breakdown_text,
                        "initial_value": f"${initial_capital:.2f}"
                    })
                    if health_report["overall_health"] == "OK":
                        health_report["overall_health"] = "WARNING"
                    if include_recommendations:
                        health_report["recommendations"].append({
                            "priority": "MEDIUM",
                            "action": "Review strategy and risk settings - account in drawdown"
                        })
                elif total_drawdown_pct > 5:
                    health_report["ok_checks"].append({
                        "category": "Account Health",
                        "check": f"Total account profitable: +{total_drawdown_pct:.1f}% ({breakdown_text})"
                    })
                else:
                    health_report["ok_checks"].append({
                        "category": "Account Health",
                        "check": f"Total account near break-even: {total_drawdown_pct:+.1f}% ({breakdown_text})"
                    })
        except Exception as e:
            logger.error(f"Account health check error: {e}")

        # === CHECK 7: Claude AI Analysis Freshness ===
        try:
            # Get Claude data from bot status (for remote Pi bot)
            claude_last_run = None

            if bot_status and 'claude' in bot_status:
                claude_info = bot_status['claude']
                claude_last_run_str = claude_info.get('last_run')

                if claude_last_run_str:
                    try:
                        # Parse "MM/DD/YYYY, HH:MM:SS AM/PM" format from status
                        claude_last_run = datetime.strptime(claude_last_run_str, "%m/%d/%Y, %I:%M:%S %p")
                    except:
                        # Try ISO format as fallback
                        try:
                            claude_last_run = datetime.fromisoformat(claude_last_run_str.replace('EST', '').replace('UTC', '').strip())
                            if claude_last_run.tzinfo is not None:
                                claude_last_run = claude_last_run.replace(tzinfo=None)
                        except Exception as e:
                            logger.warning(f"Could not parse Claude timestamp: {claude_last_run_str}, error: {e}")

            if claude_last_run:
                age_hours = (datetime.now() - claude_last_run).total_seconds() / 3600

                # Dynamic threshold based on Claude analysis schedule
                claude_schedule = config.get('claude_analysis_schedule', 'hourly')
                schedule_to_hours = {
                    'hourly': 1,
                    'two_hourly': 2,
                    'four_hourly': 4,
                    'six_hourly': 6,
                    'twice_daily': 12,
                    'daily': 24
                }
                expected_interval_hours = schedule_to_hours.get(claude_schedule, 1)
                # Warn if data is older than 1.5x the scheduled interval
                threshold_hours = expected_interval_hours * 1.5

                if age_hours > threshold_hours:
                    health_report["warnings"].append({
                        "severity": "WARNING",
                        "category": "AI Analysis",
                        "issue": f"Claude last ran {age_hours:.1f} hours ago (>{threshold_hours:.1f} hours)",
                        "impact": "May be waiting for next Claude analysis cycle or bot may be stuck",
                        "current_value": f"{age_hours:.1f} hours ago",
                        "expected_value": f"<{threshold_hours:.1f} hours (schedule: {claude_schedule}, every {expected_interval_hours}h)",
                        "note": f"Claude runs {claude_schedule}. Data age beyond 1.5x interval suggests missed cycle."
                    })
                    if health_report["overall_health"] == "OK":
                        health_report["overall_health"] = "WARNING"
                else:
                    health_report["ok_checks"].append({
                        "category": "AI Analysis",
                        "check": f"Claude ran recently ({age_hours:.1f} hours ago, threshold: {threshold_hours:.1f}h)"
                    })
            else:
                health_report["warnings"].append({
                    "severity": "WARNING",
                    "category": "AI Analysis",
                    "issue": "No Claude run time available",
                    "impact": "Cannot determine if Claude analysis is running"
                })
                if health_report["overall_health"] == "OK":
                    health_report["overall_health"] = "WARNING"
        except Exception as e:
            logger.error(f"Claude check error: {e}")

        # Add summary counts
        health_report["summary"] = {
            "critical_issues": len(health_report["issues"]),
            "warnings": len(health_report["warnings"]),
            "ok_checks": len(health_report["ok_checks"]),
            "total_checks": len(health_report["issues"]) + len(health_report["warnings"]) + len(health_report["ok_checks"])
        }

        return jsonify(health_report)

    except Exception as e:
        import traceback
        logger = logging.getLogger("CryptoBot.HealthCheck")
        logger.error(f"Health check failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            "overall_health": "ERROR",
            "error": str(e),
            "timestamp": datetime.now(EASTERN).strftime('%Y-%m-%d %H:%M:%S %Z')
        }), 500


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
