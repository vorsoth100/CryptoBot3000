"""
Flask Web Application for CryptoBot
Provides web dashboard for monitoring and control
"""

import os
import sys
import json
import threading
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading_bot import TradingBot
from src.config_manager import ConfigManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cryptobot-secret-key-change-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global bot instance
bot = None
bot_thread = None


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route('/api/status')
def get_status():
    """Get bot status"""
    if bot:
        status = bot.get_status()
        return jsonify(status)
    else:
        return jsonify({"running": False, "error": "Bot not initialized"})


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

        return jsonify({"success": True, "message": "Configuration updated"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


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
        balance = bot.coinbase.get_balance("USD")
        return jsonify({"balance_usd": balance})
    else:
        return jsonify({"balance_usd": 0})


@app.route('/api/screener')
def run_screener():
    """Run market screener"""
    if bot:
        opportunities = bot.screener.screen_coins()
        return jsonify(opportunities)
    else:
        return jsonify([])


@app.route('/api/claude/analyze', methods=['POST'])
def run_claude_analysis():
    """Trigger Claude AI analysis"""
    if not bot:
        return jsonify({"success": False, "error": "Bot not initialized"}), 400

    try:
        context = bot._build_market_context()
        analysis = bot.claude_analyst.analyze_market(context)

        if analysis:
            return jsonify({"success": True, "analysis": analysis})
        else:
            return jsonify({"success": False, "error": "Analysis failed"}), 500

    except Exception as e:
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


@app.route('/api/logs/bot')
def get_bot_logs():
    """Get bot logs"""
    try:
        log_file = "logs/bot.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                # Get last 100 lines
                lines = f.readlines()
                last_lines = lines[-100:]
                return jsonify({"logs": ''.join(last_lines)})
        else:
            return jsonify({"logs": "No logs available"})

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


def main():
    """Run Flask server"""
    print("=" * 80)
    print("CryptoBot Web Dashboard Starting...")
    print("=" * 80)
    print("Dashboard will be available at http://localhost:8779")
    print("=" * 80)

    socketio.run(app, host='0.0.0.0', port=8779, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
