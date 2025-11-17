# AI_CONTEXT.md - CryptoBot3000 Complete Documentation

**Purpose**: This document provides complete context for AI agents to understand, maintain, and develop this project.

**Last Updated**: 2025-11-17
**Current Version**: 1.16.0
**Repository**: https://github.com/vorsoth100/CryptoBot3000

---

## Table of Contents
1. [Development Workflow](#development-workflow)
2. [Version Management](#version-management)
3. [Project Architecture](#project-architecture)
4. [Core Features](#core-features)
5. [File Structure](#file-structure)
6. [API Integrations](#api-integrations)
7. [Configuration System](#configuration-system)
8. [Deployment Process](#deployment-process)
9. [Common Tasks](#common-tasks)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Change History](#change-history)

---

## Development Workflow

### Environment Setup

**Development Machine**: macOS (Mac)
**Production Machine**: Raspberry Pi 5
**Container Orchestration**: Portainer (Stacks)

### Standard Development Cycle

```
1. Develop on Mac
   ├── Edit code in /Users/dglassford/Documents/CryptoBot3000/
   ├── Test locally (optional: docker-compose up)
   └── Increment version in src/__init__.py

2. Commit to Git
   ├── git add -A
   ├── git commit -m "vX.Y.Z - Description"
   └── git push origin main

3. Deploy to Raspberry Pi
   ├── Open Portainer web interface
   ├── Navigate to Stacks > cryptobot
   ├── Click "Pull and redeploy"
   └── Verify deployment at http://<pi-ip>:8779
```

### Critical Rules for AI Agents

1. **ALWAYS increment version** in `src/__init__.py` before committing
2. **ALWAYS push to GitHub** after committing (user explicitly requires this)
3. **ALWAYS use descriptive commit messages** with version number
4. **NEVER commit sensitive data** (.env files, API keys)
5. **ALWAYS test critical changes** before committing

---

## Version Management

### Current Version: 1.16.0

### Versioning Scheme (Semantic Versioning)

```
MAJOR.MINOR.PATCH

Example: 1.16.0
         │  │  │
         │  │  └─── PATCH: Bug fixes, minor tweaks
         │  └────── MINOR: New features, non-breaking changes
         └───────── MAJOR: Breaking changes, major rewrites
```

### When to Increment

**PATCH (X.Y.Z)**
- Bug fixes
- Typo corrections
- Performance improvements
- Documentation updates
- Examples: 1.16.0 → 1.16.1

**MINOR (X.Y.0)**
- New features added
- New API integrations
- New configuration options
- UI enhancements
- Examples: 1.16.0 → 1.17.0

**MAJOR (X.0.0)**
- Breaking API changes
- Complete rewrites
- Architecture changes
- Database schema changes
- Examples: 1.16.0 → 2.0.0

### How to Increment Version

**File**: `src/__init__.py`

```python
__version__ = "1.16.0"  # Update this line
__author__ = "CryptoBot Team"
```

**Commit Message Format**:
```bash
git commit -m "$(cat <<'EOF'
vX.Y.Z - Brief description

Detailed changes:
- Change 1
- Change 2
- Change 3

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Version History (Recent)

- **1.16.0** (2025-11-17): Removed LunarCrush integration (no longer free)
- **1.15.7** (2025-11-17): Fixed LunarCrush configuration persistence
- **1.15.6** (2025-11-17): Fixed Dockerfile to avoid duplicate package installations
- **1.15.5** (2025-11-17): Fixed Dockerfile to install all requirements.txt packages
- **1.15.4** (2025-11-17): Fixed CoinGecko test endpoint, updated LunarCrush version
- **1.15.3** (2025-11-17): Fixed import errors for CoinGecko and News Sentiment
- **1.15.2** (2025-11-17): Added test buttons for all integrations
- **1.15.1** (2025-11-17): Added LunarCrush test button
- **1.15.0** (2025-11-17): Integrated LunarCrush social sentiment (later removed)

---

## Project Architecture

### Technology Stack

**Backend**:
- Python 3.9
- Flask 3.0.0 (Web server)
- Flask-SocketIO 5.3.5 (Real-time updates)
- TA-Lib 0.4.28 (Technical analysis)
- Pandas 2.1.4 (Data processing)
- NumPy 1.26.2 (Numerical operations)

**AI/ML**:
- Anthropic Claude API (claude-sonnet-4-5-20250929)

**APIs**:
- Coinbase Advanced Trade API (Trading)
- CoinGecko API (Market data - free, no key)
- Crypto Panic API (News sentiment - free tier)
- Alternative.me (Fear & Greed Index)

**Infrastructure**:
- Docker (Containerization)
- Portainer (Container management on Raspberry Pi)

### Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Dashboard (Flask)                    │
│  ┌───────────┬───────────┬───────────┬──────────────────┐   │
│  │ Dashboard │   Config  │ Claude AI │ Trades/Performance│   │
│  └───────────┴───────────┴───────────┴──────────────────┘   │
│                       (index.html + app.js)                  │
└────────────────────────────┬────────────────────────────────┘
                             │ REST API
┌────────────────────────────┴────────────────────────────────┐
│                    TradingBot (Core Engine)                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Trading Loop (Every 5 minutes)                      │    │
│  │  1. Collect market data                              │    │
│  │  2. Run screener                                     │    │
│  │  3. Get Claude analysis                              │    │
│  │  4. Execute trades (if conditions met)               │    │
│  │  5. Update positions (stop loss, take profit)        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ CoinbaseClient│ │DataCollector│ │ Screener │ │ClaudeAnalyst │
└──────────────┘ └─────────────┘ └──────────┘ └──────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐
│ RiskManager  │ │PerformanceT │ │ Signals  │ │ConfigManager │
└──────────────┘ └─────────────┘ └──────────┘ └──────────────┘
```

### Key Design Principles

1. **Modularity**: Each component has a single responsibility
2. **Configuration-Driven**: All behavior controlled via config.json
3. **Safety First**: Dry-run mode, stop losses, drawdown limits
4. **Real-time Monitoring**: SocketIO for live dashboard updates
5. **State Persistence**: All trades, positions, config stored in JSON files

---

## Core Features

### 1. Automated Trading

**Modes**:
- **Advisory**: Claude suggests, user approves manually
- **Semi-Autonomous**: Auto-execute high confidence (>80%) trades
- **Autonomous**: Auto-execute all Claude recommendations

**Safety Mechanisms**:
- Dry-run mode (simulate trades)
- Position size limits (15-25% of capital)
- Stop loss (6% default)
- Take profit (10% default)
- Max drawdown limit (20% of capital)
- Max positions limit (3 default)

### 2. Market Analysis

**Screener Modes**:
1. **Breakouts**: High volume + price momentum
2. **Oversold**: RSI <30 + volume spike
3. **Support**: Price near support level
4. **Trending**: Strong uptrend + above moving averages

**Technical Indicators** (TA-Lib):
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Moving Averages (50, 200)
- Volume analysis

**Market Data Sources**:
- CoinGecko: Trending coins, market data
- Alternative.me: Fear & Greed Index
- Crypto Panic: News sentiment
- Coinbase: Real-time price and volume data

### 3. Claude AI Integration

**Model**: claude-sonnet-4-5-20250929

**Analysis Context Provided**:
- Current portfolio state
- Screener results (top opportunities)
- Technical indicators
- Fear & Greed Index
- BTC dominance
- Trending coins (CoinGecko)
- News sentiment (Crypto Panic)
- Recent trades
- Performance metrics

**Claude's Output**:
```json
{
  "market_assessment": {
    "regime": "bull|bear|sideways",
    "confidence": 0-100,
    "key_factors": ["factor1", "factor2"],
    "risk_level": "low|medium|high"
  },
  "recommended_actions": [
    {
      "action": "buy|sell|hold",
      "coin": "BTC-USD",
      "reasoning": "Why this trade",
      "conviction": 0-100,
      "target_entry": 50000,
      "stop_loss": 47000,
      "take_profit": [52000, 55000, 60000],
      "position_size_pct": 0.20
    }
  ],
  "risk_warnings": ["warning1", "warning2"],
  "config_suggestions": [
    {
      "parameter": "stop_loss_pct",
      "current_value": 0.06,
      "suggested_value": 0.07,
      "reasoning": "Market volatility increasing"
    }
  ]
}
```

### 4. Risk Management

**Position Sizing**:
```python
# Formula
position_size = (capital * position_pct) / entry_price
max_trade_usd = capital * max_position_pct
```

**Stop Loss Management**:
- Initial stop loss: 6% below entry
- Trailing stop: Activates after 5% profit
- Emergency stop: Triggered on extreme volatility

**Drawdown Protection**:
- Monitors total portfolio value
- Halts trading if drawdown > 20%
- Requires manual reset after drawdown hit

### 5. Performance Tracking

**Metrics Calculated**:
- Win rate (% profitable trades)
- Profit factor (total wins / total losses)
- Average win/loss amounts
- Max drawdown
- Total fees paid
- Return vs BTC buy-and-hold

**Trade Logging**:
- CSV format: `logs/trades.csv`
- Fields: timestamp, product, action, quantity, price, fee, profit

---

## File Structure

```
CryptoBot3000/
│
├── src/                           # Python source code
│   ├── __init__.py               # Version: 1.16.0
│   ├── trading_bot.py            # Main bot engine (560 lines)
│   ├── coinbase_client.py        # Coinbase API wrapper
│   ├── data_collector.py         # Market data collection
│   ├── signals.py                # Technical indicators (TA-Lib)
│   ├── screener.py               # Market screener
│   ├── risk_manager.py           # Position sizing, stops
│   ├── performance_tracker.py    # P&L tracking
│   ├── claude_analyst.py         # Claude AI integration
│   ├── config_manager.py         # Configuration management
│   ├── coingecko_data.py         # CoinGecko API client
│   ├── news_sentiment.py         # Crypto Panic integration
│   ├── telegram_bot.py           # Telegram notifications (optional)
│   └── utils.py                  # Utilities (rate limiter, etc)
│
├── web/                           # Flask web application
│   ├── app.py                    # Flask server (800+ lines)
│   ├── templates/
│   │   └── index.html            # Dashboard HTML (2800+ lines)
│   └── static/
│       ├── css/
│       │   └── styles.css        # Dashboard styles
│       └── js/
│           └── app.js            # Dashboard JavaScript (2600+ lines)
│
├── logs/                          # Log files (not in git)
│   ├── bot.log                   # Bot execution log
│   └── trades.csv                # Trade history CSV
│
├── data/                          # Data files (not in git)
│   ├── config.json               # Bot configuration
│   ├── positions.json            # Current positions
│   └── claude_recommendations/   # Claude analysis history
│
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Local Docker Compose
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
├── .gitignore                     # Git ignore rules
├── README.md                      # User documentation
└── AI_CONTEXT.md                  # This file
```

### Key Files Explained

**src/trading_bot.py**:
- Main bot loop (runs every 5 minutes)
- Orchestrates all other components
- Executes trades based on Claude recommendations
- Updates positions (stop loss, take profit checks)

**src/claude_analyst.py**:
- Sends market context to Claude API
- Parses Claude's JSON responses
- Validates recommendations
- Stores analysis history

**web/app.py**:
- Flask REST API (30+ endpoints)
- Serves dashboard UI
- Real-time SocketIO updates
- API test endpoints

**web/templates/index.html**:
- Single-page application
- 6 tabs: Dashboard, Config, Claude AI, Trades, Performance, Debug
- Configuration presets (Conservative, Moderate, Aggressive)

**src/config_manager.py**:
- Loads/saves configuration
- Provides defaults
- Validates settings
- Located at: `data/config.json`

---

## API Integrations

### 1. Coinbase Advanced Trade API

**Authentication**: API Key + Secret (Cloud API Keys)

**Endpoints Used**:
- `GET /api/v3/brokerage/accounts` - Get account balances
- `GET /api/v3/brokerage/orders/historical/batch` - Get order history
- `GET /api/v3/brokerage/products` - Get trading pairs
- `GET /api/v3/brokerage/products/{product_id}/candles` - Get price history
- `POST /api/v3/brokerage/orders` - Place orders
- `GET /api/v3/brokerage/orders/historical/{order_id}` - Get order status

**Rate Limits**:
- 30 requests per second (public)
- 30 requests per second (private)
- Enforced with RateLimiter in utils.py

**Fee Structure**:
- Maker: 0.5% (limit orders)
- Taker: 2.0% (market orders)
- Bot prioritizes limit orders when possible

### 2. Anthropic Claude API

**Authentication**: API Key (in header)

**Model**: claude-sonnet-4-5-20250929

**Endpoint**: `POST https://api.anthropic.com/v1/messages`

**Request Format**:
```python
{
    "model": "claude-sonnet-4-5-20250929",
    "max_tokens": 4000,
    "messages": [
        {
            "role": "user",
            "content": "Market analysis prompt with JSON context"
        }
    ]
}
```

**Response Parsing**:
- Expects JSON in Claude's response
- Validates structure against expected schema
- Handles parse errors gracefully

**Cost Optimization**:
- Analysis runs only when requested (not automatic)
- Caches responses for 5 minutes
- Provides context summarization

### 3. CoinGecko API (Free Tier)

**Authentication**: None required

**Endpoints Used**:
- `GET /api/v3/search/trending` - Trending coins
- `GET /api/v3/simple/price` - Current prices
- `GET /api/v3/global` - BTC dominance

**Rate Limits**:
- 10-50 calls/minute (free tier)
- Bot caches responses for 10 minutes

**Class**: `CoinGeckoCollector` in `src/coingecko_data.py`

### 4. Crypto Panic API (Free Tier)

**Authentication**: None required (free tier has no key)

**Endpoint**: `GET https://cryptopanic.com/api/v1/posts/`

**Rate Limits**:
- Very strict on free tier (few calls per minute)
- Bot caches aggressively (30 minutes)

**Sentiment Scoring**:
- Parses news titles for positive/negative keywords
- Calculates sentiment score: -100 (bearish) to +100 (bullish)

**Class**: `NewsSentiment` in `src/news_sentiment.py`

### 5. Alternative.me API (Free)

**Endpoint**: `GET https://api.alternative.me/fng/`

**Returns**: Fear & Greed Index (0-100)
- 0-24: Extreme Fear
- 25-44: Fear
- 45-55: Neutral
- 56-75: Greed
- 76-100: Extreme Greed

**Usage**: Influences Claude's risk assessment

---

## Configuration System

### Configuration File: `data/config.json`

**Default Configuration**:
```json
{
  "dry_run": true,
  "initial_capital": 600.0,
  "min_trade_usd": 150.0,
  "max_positions": 3,
  "max_position_pct": 0.25,
  "stop_loss_pct": 0.06,
  "take_profit_pct": 0.10,
  "max_drawdown_pct": 0.20,
  "trailing_stop_enabled": true,
  "trailing_stop_trigger_pct": 0.05,
  "trailing_stop_distance_pct": 0.03,
  "partial_profit_enabled": true,
  "partial_profit_trigger_pct": 0.05,
  "partial_profit_amount_pct": 0.50,

  "coinbase_maker_fee": 0.005,
  "coinbase_taker_fee": 0.02,
  "max_fee_pct": 0.025,

  "claude_enabled": true,
  "claude_analysis_mode": "advisory",
  "claude_model": "claude-sonnet-4-5-20250929",
  "claude_confidence_threshold": 80,

  "screener_enabled": true,
  "screener_mode": "breakouts",
  "screener_max_results": 10,

  "coingecko_enabled": true,
  "coingecko_cache_minutes": 10,
  "coingecko_trending_boost": 5,
  "coingecko_sentiment_boost": 3,
  "coingecko_social_boost": 2,

  "news_sentiment_enabled": false,
  "news_sentiment_cache_minutes": 30,

  "telegram_enabled": false,
  "telegram_bot_token": "",
  "telegram_chat_id": "",
  "telegram_notify_trades": true,
  "telegram_notify_claude": true,
  "telegram_daily_summary": true
}
```

### Configuration Presets

**Conservative** (Best for $600 capital):
```json
{
  "max_positions": 2,
  "max_position_pct": 0.20,
  "stop_loss_pct": 0.07,
  "take_profit_pct": 0.12,
  "claude_confidence_threshold": 85,
  "screener_max_results": 5
}
```

**Moderate** (Default):
```json
{
  "max_positions": 3,
  "max_position_pct": 0.25,
  "stop_loss_pct": 0.06,
  "take_profit_pct": 0.10,
  "claude_confidence_threshold": 75,
  "screener_max_results": 10
}
```

**Aggressive** (Higher risk):
```json
{
  "max_positions": 4,
  "max_position_pct": 0.30,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.15,
  "claude_confidence_threshold": 70,
  "screener_max_results": 20
}
```

### Environment Variables (.env)

**NEVER commit .env to Git!**

**Required**:
```env
COINBASE_API_KEY=organizations/your-org-id/apiKeys/your-key-id
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**Optional**:
```env
EMAIL_ADDRESS=your-email@example.com
EMAIL_PASSWORD=your-app-password
```

### Portainer Environment Configuration

**In Portainer Stack**:
1. Go to Stacks > cryptobot
2. Scroll to "Environment variables"
3. Add:
   - `COINBASE_API_KEY`
   - `COINBASE_API_SECRET`
   - `ANTHROPIC_API_KEY`

**Note**: Values are stored securely in Portainer, not in Git.

---

## Deployment Process

### Development on Mac

**Location**: `/Users/dglassford/Documents/CryptoBot3000/`

**Local Testing** (Optional):
```bash
cd /Users/dglassford/Documents/CryptoBot3000
docker-compose up -d
# Access at http://localhost:8779
docker-compose down
```

### Commit to Git

**Pre-commit Checklist**:
1. ✅ Version incremented in `src/__init__.py`
2. ✅ No sensitive data (check .gitignore)
3. ✅ Code tested (at least basic functionality)
4. ✅ Commit message includes version number

**Commit and Push**:
```bash
git add -A
git commit -m "vX.Y.Z - Description of changes"
git push origin main
```

### Deploy to Raspberry Pi

**Steps**:
1. Open Portainer web interface: `http://<pi-ip>:9000`
2. Navigate to: **Stacks** > **cryptobot**
3. Click: **Pull and redeploy**
4. Wait for rebuild (takes 5-10 minutes due to TA-Lib compilation)
5. Verify deployment: `http://<pi-ip>:8779`

**Portainer Stack Configuration**:
```yaml
version: '3.8'

services:
  cryptobot:
    build: .
    container_name: cryptobot
    restart: unless-stopped
    ports:
      - "8779:8779"
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    environment:
      - COINBASE_API_KEY=${COINBASE_API_KEY}
      - COINBASE_API_SECRET=${COINBASE_API_SECRET}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

### Docker Build Process

**Dockerfile Explanation**:
1. Base image: `python:3.9-slim`
2. Install system dependencies (build-essential, wget)
3. Install TA-Lib C library (compile from source)
4. Copy requirements.txt
5. Install Python packages:
   - Install numpy first
   - Install TA-Lib with library paths
   - Install remaining packages from requirements.txt (filtered)
6. Copy application code
7. Expose port 8779
8. Run Flask app: `python web/app.py`

**Build Time**: 5-10 minutes on Raspberry Pi 5

---

## Common Tasks

### Adding a New Feature

**Process**:
1. Determine version increment (minor for features)
2. Implement feature
3. Update `src/__init__.py` version
4. Test locally
5. Update this AI_CONTEXT.md (add to Change History)
6. Commit with descriptive message
7. Push to GitHub
8. Deploy via Portainer

### Fixing a Bug

**Process**:
1. Identify bug location
2. Implement fix
3. Increment PATCH version in `src/__init__.py`
4. Test fix
5. Commit: `vX.Y.Z - Fix: [bug description]`
6. Push to GitHub
7. Deploy via Portainer

### Adding a New API Integration

**Steps**:
1. Create new client file: `src/new_api_client.py`
2. Add configuration options to `src/config_manager.py`
3. Add API to requirements.txt (if needed)
4. Integrate into `src/trading_bot.py`
5. Add to Claude context in `src/claude_analyst.py`
6. Add test endpoint to `web/app.py`
7. Add test button to `web/templates/index.html`
8. Add test function to `web/static/js/app.js`
9. Update version (MINOR)
10. Update this AI_CONTEXT.md
11. Commit and deploy

### Updating Configuration

**Web Dashboard**:
1. Navigate to Configuration tab
2. Modify settings
3. Click "Save Configuration"
4. Reload bot (if running)

**Direct File Edit** (Advanced):
```bash
# On Raspberry Pi
nano data/config.json
# Edit values
# Restart container
docker restart cryptobot
```

### Checking Logs

**Via Dashboard**:
- Navigate to Debug tab
- Click "Refresh Logs"

**Via Docker**:
```bash
# Real-time logs
docker logs -f cryptobot

# Last 100 lines
docker logs --tail 100 cryptobot
```

**Via File System**:
```bash
# Bot logs
cat logs/bot.log

# Trade history
cat logs/trades.csv
```

### Testing API Connections

**Via Dashboard**:
1. Navigate to Debug tab
2. Click test buttons:
   - Test Coinbase API
   - Test Claude API
   - Test CoinGecko API
   - Test News Sentiment API

**Via Command Line**:
```bash
# Test from within container
docker exec cryptobot python -c "from src.coinbase_client import CoinbaseClient; print('OK')"
```

---

## Troubleshooting Guide

### Issue: Bot Won't Start

**Symptoms**:
- Container keeps restarting
- Dashboard not accessible

**Solutions**:
1. Check logs: `docker logs cryptobot`
2. Verify API keys in Portainer environment variables
3. Check port 8779 is not in use
4. Verify TA-Lib compiled correctly (common issue)

**TA-Lib Fix**:
```dockerfile
# In Dockerfile, verify these lines exist:
RUN wget https://sourceforge.net/projects/ta-lib/files/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz/download -O ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr --build=aarch64-unknown-linux-gnu && \
    make && \
    make install
```

### Issue: "No module named 'talib'"

**Cause**: TA-Lib not installed or library path incorrect

**Solution**:
1. Rebuild Docker image: `docker-compose build --no-cache`
2. Verify LD_LIBRARY_PATH in Dockerfile:
   ```dockerfile
   ENV LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
   ```

### Issue: Coinbase API Errors

**Symptoms**:
- "Invalid API key"
- "Signature verification failed"

**Solutions**:
1. Verify API key format in Portainer:
   ```
   COINBASE_API_KEY=organizations/.../apiKeys/...
   ```
2. Verify private key includes newlines:
   ```
   -----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----
   ```
3. Check API key permissions (needs trading enabled)
4. Verify API key not expired

### Issue: Claude API Errors

**Symptoms**:
- "Invalid API key"
- "Rate limit exceeded"

**Solutions**:
1. Check API key format: `sk-ant-api03-...`
2. Verify account has credits
3. Check rate limits (Claude has per-minute limits)
4. Wait 1 minute and retry

### Issue: Configuration Not Saving

**Symptoms**:
- Changes revert after refresh
- "Error saving configuration" message

**Solutions**:
1. Check file permissions: `data/config.json` must be writable
2. Verify JSON validity (use JSON validator)
3. Check Docker volume mount: `-v ./data:/app/data`
4. Restart container after major config changes

### Issue: Positions Not Updating

**Symptoms**:
- Stop loss not triggering
- Take profit not executing
- Stale position data

**Solutions**:
1. Check bot is running: Bot Status in dashboard
2. Verify Coinbase API connection
3. Check logs for errors
4. Manually close positions if needed

### Issue: "Port 8779 Already in Use"

**Solution**:
```bash
# Find process using port
lsof -i :8779

# Kill process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8780:8779"
```

---

## Change History

### v1.16.0 (2025-11-17)
**Major Change**: Removed LunarCrush integration
- **Reason**: LunarCrush no longer free ($24/month minimum)
- **Files Changed**: 9 files, 444 lines removed
- **Removed**:
  - `src/lunarcrush_client.py`
  - LunarCrush config options
  - LunarCrush from Claude prompts
  - LunarCrush UI elements
  - `/api/test/lunarcrush` endpoint
- **Impact**: No functionality loss (CoinGecko + News Sentiment still available)

### v1.15.7 (2025-11-17)
**Bug Fix**: LunarCrush configuration not persisting
- Fixed: `lunarcrush_enabled` not saved/loaded in JavaScript
- Added to `saveConfig()` and `loadConfig()` functions

### v1.15.6 (2025-11-17)
**Bug Fix**: Docker build failure
- Fixed: Dockerfile filtered numpy and TA-Lib from requirements.txt
- Reason: These packages installed separately with special flags

### v1.15.5 (2025-11-17)
**Bug Fix**: LunarCrush not installing
- Fixed: Dockerfile now uses `pip install -r requirements.txt`
- Previous: Hardcoded package list (missed new packages)

### v1.15.4 (2025-11-17)
**Bug Fixes**: API test endpoints
- Fixed: CoinGeckoCollector missing 'enabled' attribute
- Updated: LunarCrush from 2.0.2 to 2.0.5

### v1.15.3 (2025-11-17)
**Bug Fixes**: Import errors
- Fixed: CoinGecko import (coingecko_client → coingecko_data)
- Fixed: News Sentiment import (NewsSentimentAnalyzer → NewsSentiment)

### v1.15.2 (2025-11-17)
**Feature**: Added test buttons for all integrations
- Added: Test LunarCrush button
- Added: Test CoinGecko button
- Added: Test News Sentiment button
- Fixed: Claude AI banner navigation

### v1.15.1 (2025-11-17)
**Feature**: LunarCrush test endpoint
- Added: `/api/test/lunarcrush` endpoint
- Added: `testLunarCrush()` JavaScript function
- Added: Test button in Debug tab

### v1.15.0 (2025-11-17)
**Feature**: LunarCrush social sentiment integration
- Added: `src/lunarcrush_client.py`
- Added: LunarCrush to Claude analysis context
- Added: Configuration options for LunarCrush
- Added: UI toggle for LunarCrush
- **Note**: Later removed in v1.16.0

---

## Additional Notes for AI Agents

### Code Style Guidelines

**Python**:
- Follow PEP 8
- Use type hints where possible
- Docstrings for all functions
- Logging instead of print statements

**JavaScript**:
- Use async/await for API calls
- Clear variable names
- Add comments for complex logic

**Commit Messages**:
- Start with version: "vX.Y.Z - "
- Include emoji: 🤖 for AI-generated
- Add Co-Authored-By: Claude

### Testing Checklist

Before committing:
1. ✅ Test API connections (via Debug tab)
2. ✅ Verify configuration saves
3. ✅ Check no console errors
4. ✅ Verify version incremented
5. ✅ Test on Mac (if possible)

### Important Files to Never Modify Manually

- `logs/trades.csv` (generated by bot)
- `data/positions.json` (managed by bot)
- `data/claude_recommendations/*.json` (Claude history)

### Files That Should Be Modified Together

When changing configuration:
- `src/config_manager.py` (defaults)
- `web/templates/index.html` (form fields)
- `web/static/js/app.js` (saveConfig/loadConfig)

When adding API integration:
- Create `src/new_api_client.py`
- Update `src/config_manager.py`
- Update `src/trading_bot.py`
- Update `src/claude_analyst.py`
- Update `web/app.py` (test endpoint)
- Update `web/templates/index.html` (test button)
- Update `web/static/js/app.js` (test function)

### User Preferences (From Session History)

1. **ALWAYS push to GitHub after commits** (user explicitly stated)
2. Version must be incremented before every commit
3. User prefers detailed commit messages with change lists
4. User develops on Mac, deploys to Raspberry Pi via Portainer
5. User manually pulls from GitHub (no auto-deploy webhooks)
6. Environment variables stored in Portainer (not .env on Pi)

---

## Quick Reference Commands

### Git Workflow
```bash
# Standard commit
git add -A
git commit -m "vX.Y.Z - Description"
git push origin main

# Check status
git status
git log --oneline -5

# Undo last commit (if not pushed)
git reset --soft HEAD~1
```

### Docker Commands
```bash
# Build and run locally
docker-compose up -d
docker-compose down
docker-compose logs -f

# Raspberry Pi commands
docker ps                    # List containers
docker logs cryptobot        # View logs
docker restart cryptobot     # Restart bot
docker exec -it cryptobot bash  # Shell into container
```

### File Locations
```bash
# Mac
/Users/dglassford/Documents/CryptoBot3000/

# Raspberry Pi (inside container)
/app/

# Configuration
/app/data/config.json

# Logs
/app/logs/bot.log
/app/logs/trades.csv
```

---

## End of AI_CONTEXT.md

**For AI Agents**: You now have complete context to:
- Understand the project architecture
- Make code changes
- Fix bugs
- Add features
- Deploy to production
- Debug issues

**Remember**:
1. Always increment version
2. Always push to GitHub
3. Test before committing
4. Update this file for major changes

**Questions?** Refer to README.md for user documentation.

**Current Status**: v1.16.0 - Production ready, deployed on Raspberry Pi 5
