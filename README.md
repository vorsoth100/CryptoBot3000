# 🤖 CryptoBot - AI-Powered Cryptocurrency Trading Bot

An automated cryptocurrency trading bot for Coinbase Advanced Trade API with Claude AI integration. Designed for 24/7 operation with intelligent risk management and comprehensive web dashboard.

## 🌟 Features

- **Coinbase Advanced Trade Integration** - Direct API integration for live trading
- **Claude AI Analysis** - Daily market analysis and trade recommendations from Anthropic's Claude
- **Technical Analysis** - TA-Lib indicators (RSI, MACD, Bollinger Bands, Moving Averages)
- **Market Screener** - Multi-mode screening (breakouts, oversold, support, trending)
- **Risk Management** - Position sizing, stop losses, trailing stops, partial profits
- **Performance Tracking** - Complete trade history, P&L tracking, metrics
- **Web Dashboard** - Real-time monitoring and control via Flask web interface
- **Docker Ready** - Fully containerized for easy deployment
- **Portainer Compatible** - Deploy to Raspberry Pi 5 via Portainer

## 📋 Requirements

- Python 3.9+
- Docker & Docker Compose (for containerized deployment)
- Coinbase Advanced Trade API credentials
- Anthropic Claude API key
- $600 starting capital (configurable)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone <your-repo-url>
cd CryptoBot3000
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Coinbase Advanced Trade API
COINBASE_API_KEY=your_api_key_here
COINBASE_API_SECRET=your_api_secret_here

# Claude AI
ANTHROPIC_API_KEY=your_anthropic_key_here
```

### 3. Docker Deployment (Recommended)

#### Option A: Docker Compose (Local)

```bash
docker-compose up -d
```

#### Option B: Portainer (Raspberry Pi 5)

1. Build the image on your Raspberry Pi:
   ```bash
   docker build -t cryptobot:latest .
   ```

2. In Portainer:
   - Go to **Stacks** > **Add Stack**
   - Name it `cryptobot`
   - Paste content from `portainer-stack.yml`
   - Update volume paths and API keys
   - Click **Deploy the stack**

3. Access dashboard at: `http://<raspberry-pi-ip>:8779`

### 4. Manual Installation (Non-Docker)

```bash
# Install TA-Lib (required)
# On macOS:
brew install ta-lib

# On Ubuntu/Debian:
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# Install Python dependencies
pip install -r requirements.txt

# Run web dashboard
python web/app.py
```

## 🎮 Usage

### Web Dashboard

Access the dashboard at `http://localhost:8779`

**Tabs:**
- **Dashboard** - Portfolio overview, positions, recent trades
- **Configuration** - All bot settings with presets (Conservative, Moderate, Aggressive)
- **Claude AI** - Run analysis, view recommendations
- **Trades** - Complete trade history
- **Performance** - Metrics, win rate, profit factor
- **Debug** - API tests, logs

### Configuration Presets

**Conservative** (Recommended for $600 capital)
- 2 max positions
- 7% stop loss
- 85%+ confidence trades only
- Focus on BTC/ETH

**Moderate** (Default)
- 3 max positions
- 6% stop loss
- 75%+ confidence trades
- Top 10 coins

**Aggressive** (Higher risk)
- 4 max positions
- 5% stop loss
- 70%+ confidence trades
- Top 20 coins

### Claude AI Modes

1. **Advisory** - Claude suggests, you approve (safest)
2. **Semi-Autonomous** - Auto-execute high confidence (>80%) trades
3. **Autonomous** - Auto-execute all recommendations (not recommended initially)

## 📊 Trading Strategy

### Risk Management
- **Stop Loss**: 6% max loss per position
- **Position Size**: 15-25% of capital per trade
- **Max Positions**: 3-4 concurrent
- **Max Drawdown**: 20% total ($120 loss limit)
- **Fee Awareness**: Prioritizes limit orders (0.5%) over market (2%)

### Market Screening
- **Breakouts**: High volume + momentum
- **Oversold**: RSI <30 + volume spike
- **Support**: Price near support with bullish signals
- **Trending**: Strong uptrend + above MAs

### Technical Indicators
- RSI (14-period): Overbought/oversold
- MACD (12,26,9): Trend strength
- Bollinger Bands (20,2): Volatility
- Moving Averages (50,200): Trend direction
- Volume analysis: Spike detection

## 🔒 Security

- API keys stored in `.env` (never commit to Git)
- Dry-run mode enabled by default
- Stop loss protection on all positions
- Drawdown limits to prevent catastrophic loss
- Rate limiting on all APIs

## 📁 Project Structure

```
CryptoBot3000/
├── src/
│   ├── trading_bot.py          # Main bot engine
│   ├── coinbase_client.py      # Coinbase API wrapper
│   ├── data_collector.py       # Market data (CoinGecko, Fear & Greed)
│   ├── signals.py              # TA-Lib indicators
│   ├── screener.py             # Market screener
│   ├── risk_manager.py         # Position sizing, stops
│   ├── performance_tracker.py  # P&L tracking
│   ├── claude_analyst.py       # Claude AI integration
│   ├── config_manager.py       # Configuration handling
│   └── utils.py                # Helpers, rate limiter
├── web/
│   ├── app.py                  # Flask server
│   ├── templates/
│   │   └── index.html          # Dashboard UI
│   └── static/
│       ├── css/styles.css
│       └── js/app.js
├── logs/                       # Trade logs, bot logs
├── data/                       # Configuration, Claude recommendations
├── Dockerfile
├── docker-compose.yml
├── portainer-stack.yml
├── requirements.txt
└── README.md
```

## 🧪 Testing

### 1. Test Connections

Use the **Debug** tab in the dashboard:
- Test Coinbase API
- Test Claude API

### 2. Paper Trading

Set `dry_run: true` in configuration. This simulates all trades without executing.

Recommended: Run in dry-run mode for 7-30 days before going live.

### 3. Start Small

When going live:
1. Start with $50-100 (not full $600)
2. Use Conservative preset
3. Monitor first 3-5 trades closely
4. Scale up only after success

## 📝 Configuration

All settings are configurable via the web dashboard.

**Key Settings:**

| Setting | Default | Description |
|---------|---------|-------------|
| `dry_run` | `true` | Simulate trades without executing |
| `initial_capital` | `600.0` | Starting capital in USD |
| `min_trade_usd` | `150.0` | Minimum trade size |
| `max_positions` | `3` | Max concurrent positions |
| `stop_loss_pct` | `0.06` | 6% stop loss |
| `take_profit_pct` | `0.10` | 10% take profit |
| `claude_analysis_mode` | `advisory` | advisory/semi_autonomous/autonomous |
| `claude_confidence_threshold` | `80` | Min confidence for auto-execution |

See `data/config.json` for all settings.

## 🐛 Troubleshooting

### Bot Won't Start

1. Check API credentials in `.env`
2. Verify Coinbase API has trading permissions
3. Check logs: `logs/bot.log`

### "Connection Failed" Errors

- Verify internet connection
- Check API rate limits
- Ensure API keys are correct

### TA-Lib Import Error

Install TA-Lib system library:
```bash
# macOS
brew install ta-lib

# Ubuntu/Debian
sudo apt-get install libta-lib-dev
```

### Port 8779 Already in Use

Change port in `docker-compose.yml` or `portainer-stack.yml`:
```yaml
ports:
  - "8780:8779"  # Changed from 8779
```

## 📈 Performance Metrics

The bot tracks:
- **Win Rate**: % of profitable trades
- **Profit Factor**: Total wins / Total losses
- **Average Win/Loss**: Mean P&L per trade
- **Max Drawdown**: Largest peak-to-trough decline
- **Total Fees**: All fees paid
- **Return vs BTC**: Performance vs buy-and-hold

## ⚠️ Disclaimer

**This bot trades with real money. Use at your own risk.**

- Cryptocurrency trading is highly risky
- Past performance does not guarantee future results
- Only trade with money you can afford to lose
- Start with paper trading (dry-run mode)
- Monitor the bot regularly
- The developers are not responsible for any financial losses

## 🛣️ Roadmap

**V2 Features (Future):**
- [ ] Multi-exchange support (Binance, Kraken)
- [ ] Advanced on-chain metrics
- [ ] ML price predictions
- [ ] Twitter/Reddit sentiment analysis
- [ ] Mobile app for monitoring
- [ ] Telegram/Discord alerts
- [ ] Tax loss harvesting
- [ ] Backtesting framework

## 📚 Resources

- [Coinbase Advanced Trade API Docs](https://docs.cloud.coinbase.com/advanced-trade-api/docs)
- [Anthropic Claude API Docs](https://docs.anthropic.com/)
- [TA-Lib Documentation](https://ta-lib.org/)
- [CoinGecko API](https://www.coingecko.com/en/api)

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- Built with Python, Flask, TA-Lib, and Claude AI
- Inspired by the need for intelligent, automated crypto trading
- Thanks to the open-source community

---

**Good luck and trade safely! 🚀**

For questions or issues, please open a GitHub issue.
