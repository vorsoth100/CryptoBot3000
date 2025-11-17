# CryptoBot3000 Integrations Guide

## Telegram Bot Integration

### Overview
CryptoBot3000 now includes full Telegram bot integration for real-time notifications and remote bot control via Telegram.

### Features
- 📱 Real-time trade notifications (entries, exits, P&L)
- 🤖 Claude AI analysis summaries
- 📊 Daily performance reports
- 🎯 Stop loss & take profit alerts
- ⚠️ Error notifications
- 🎮 Bot control commands (/status, /pause, /resume, /positions, /performance)

### Setup Instructions

#### Step 1: Create a Telegram Bot
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts to choose a name and username for your bot
4. **Save the bot token** provided by BotFather (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### Step 2: Get Your Chat ID
1. Start a conversation with your new bot (click the link provided by BotFather or search for your bot's username)
2. Send any message to your bot (e.g., "Hello")
3. Visit this URL in your browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":YOUR_CHAT_ID}` in the JSON response
5. **Save your chat ID** (it's a number, may be negative)

#### Step 3: Configure CryptoBot3000
1. Open the CryptoBot web dashboard (http://YOUR_IP:8779)
2. Navigate to the **Configuration** tab
3. Scroll to the **Telegram Bot Integration** section
4. Enable Telegram by checking the box
5. Paste your **Bot Token** and **Chat ID**
6. Configure notification preferences (trades, Claude analysis, daily summary)
7. Click **Save Configuration**
8. Restart the bot for changes to take effect

#### Step 4: Install Required Library
SSH into your Raspberry Pi and install the Telegram library:
```bash
cd /path/to/CryptoBot3000
pip3 install python-telegram-bot
# Or if using Docker:
docker exec -it cryptobot pip install python-telegram-bot
```

### Available Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and overview |
| `/help` | List all available commands |
| `/status` | Show bot status (running, mode, positions) |
| `/positions` | List all active positions with P&L |
| `/performance` | Performance metrics summary |
| `/pause` | Pause trading bot |
| `/resume` | Resume trading bot |

### Example Notifications

**Trade Entry:**
```
🟢 Trade Entry

Symbol: BTC-USD
Side: BUY
Price: $50,000.00
Size: 0.003

Time: 2025-11-16 19:30:00 EST
```

**Trade Exit:**
```
✅ Trade Exit

Symbol: BTC-USD
Side: SELL
Entry: $50,000.00
Exit: $51,500.00
P&L: $4.50 (+3.00%)
Reason: Take profit hit

Time: 2025-11-16 21:15:00 EST
```

**Daily Summary:**
```
📈 Daily Summary

Return: +2.45%
Trades: 5
Win Rate: 80.0%
Best: BTC-USD (+3.00%)
Worst: ETH-USD (-0.50%)

Date: 2025-11-16
```

### Troubleshooting

**Bot not responding to commands:**
- Verify bot token is correct
- Ensure chat ID is correct (check for negative sign if present)
- Check that `python-telegram-bot` library is installed
- Review logs: `docker logs cryptobot` or check `logs/bot.log`

**Not receiving notifications:**
- Verify Telegram is enabled in configuration
- Check specific notification toggles (trades, Claude, etc.)
- Ensure bot is actually running trades (not paused)
- Review logs for Telegram errors

---

## TradingView Webhook Integration

### Overview
Execute trades automatically based on TradingView alerts and custom indicators using webhooks.

### Features
- 📊 Execute trades from TradingView alerts
- 🔐 Secure webhook authentication
- ✅ Technical indicator confirmation (optional)
- 📝 Signal logging (can disable auto-execution)
- 🛡️ RSI/MACD confirmation to filter bad signals

### Setup Instructions

#### Step 1: Generate Webhook Secret
Generate a secure random string to use as your webhook secret. Use a password generator or run:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
**Save this secret** - you'll need it for both CryptoBot and TradingView.

#### Step 2: Configure CryptoBot3000
1. Open the web dashboard (http://YOUR_IP:8779)
2. Navigate to the **Configuration** tab
3. Scroll to the **TradingView Webhook Integration** section
4. Enable TradingView Webhooks
5. Paste your **Webhook Secret Key**
6. Configure options:
   - **Auto-Execute Signals**: Enable to automatically execute trades (disable to log only)
   - **Require Technical Confirmation**: Enable to reject signals that conflict with RSI/MACD
7. **Note the Webhook URL** displayed (e.g., `http://YOUR_IP:8779/api/tradingview/webhook`)
8. Click **Save Configuration**

#### Step 3: Set Up Port Forwarding (if accessing remotely)
If your TradingView alerts need to reach your bot from the internet:
1. Log in to your router admin panel
2. Forward external port (e.g., 8779) to your Raspberry Pi's local IP:8779
3. Use your public IP or DDNS hostname in the webhook URL
4. **Security**: Only use HTTPS in production, consider VPN or Tailscale for secure access

#### Step 4: Create TradingView Alert
1. Open TradingView and create your strategy/indicator
2. Click the **Alert** button (clock icon)
3. Set your alert conditions
4. In the **Notifications** tab:
   - Enable **Webhook URL**
   - Paste your webhook URL: `http://YOUR_IP:8779/api/tradingview/webhook`
5. In the **Message** field, use this JSON format:
   ```json
   {
     "secret": "YOUR_WEBHOOK_SECRET_HERE",
     "action": "buy",
     "symbol": "{{ticker}}",
     "price": {{close}},
     "size_usd": 150,
     "message": "{{strategy.order.action}} signal on {{ticker}}"
   }
   ```
6. Create the alert

### Webhook JSON Format

**Required Fields:**
- `secret`: Your webhook secret key for authentication
- `action`: `"buy"` or `"sell"`
- `symbol`: Product ID (e.g., `"BTC-USD"`)

**Optional Fields:**
- `price`: Current price (for logging)
- `size_usd`: Trade size in USD (defaults to `min_trade_usd` config)
- `message`: Custom message to log with the trade

### Example Webhook Payloads

**Buy Signal:**
```json
{
  "secret": "your_webhook_secret_here",
  "action": "buy",
  "symbol": "BTC-USD",
  "price": 50000.00,
  "size_usd": 200.00,
  "message": "RSI oversold + MACD crossover"
}
```

**Sell Signal:**
```json
{
  "secret": "your_webhook_secret_here",
  "action": "sell",
  "symbol": "BTC-USD",
  "price": 51500.00,
  "message": "Take profit target reached"
}
```

### TradingView Alert Message Templates

**Simple Buy/Sell:**
```
{
  "secret": "YOUR_SECRET",
  "action": "{{strategy.order.action}}",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "message": "Signal: {{strategy.order.action}} {{ticker}} at {{close}}"
}
```

**With Dynamic Sizing:**
```
{
  "secret": "YOUR_SECRET",
  "action": "buy",
  "symbol": "{{ticker}}",
  "price": {{close}},
  "size_usd": 150,
  "message": "{{strategy.order.comment}}"
}
```

### Technical Confirmation

When **Require Technical Confirmation** is enabled, signals are validated against current market conditions:

**Buy Signal Rejections:**
- RSI > 70 (overbought)
- MACD below signal line (bearish)

**Sell Signal Rejections:**
- RSI < 30 (oversold)

This helps filter out low-quality signals and prevent trades in adverse conditions.

### Security Best Practices

1. **Use a strong webhook secret** (32+ characters, random)
2. **Never share your webhook secret** publicly
3. **Use HTTPS** if exposing to internet (consider reverse proxy with SSL)
4. **Whitelist IPs** if possible (TradingView webhook IPs)
5. **Monitor logs** for unauthorized access attempts
6. **Test with auto-execute disabled** first (log-only mode)
7. **Consider VPN/Tailscale** for secure remote access instead of port forwarding

### Testing Your Webhook

Test with curl command:
```bash
curl -X POST http://YOUR_IP:8779/api/tradingview/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "YOUR_SECRET",
    "action": "buy",
    "symbol": "BTC-USD",
    "price": 50000,
    "size_usd": 150,
    "message": "Test signal"
  }'
```

Expected response (auto-trade disabled):
```json
{
  "success": true,
  "message": "Signal received but auto-trade is disabled",
  "action": "buy",
  "symbol": "BTC-USD",
  "executed": false
}
```

### Troubleshooting

**Webhook not receiving alerts:**
- Verify webhook URL is correct and accessible
- Check firewall/port forwarding settings
- Test with curl command first
- Check TradingView alert is active and has triggered

**Authentication failures:**
- Verify webhook secret matches in both config and TradingView
- Check for extra spaces or quotes in secret
- Review logs for authentication errors

**Signals rejected:**
- Check if auto-trade is enabled
- Review technical confirmation settings
- Check logs for specific rejection reason (RSI/MACD)

**Trades not executing:**
- Verify bot is running and not paused
- Check dry_run mode setting
- Ensure sufficient balance
- Review risk management limits (max positions, drawdown)

### Monitoring

Monitor webhook activity in bot logs:
```bash
# Docker
docker logs -f cryptobot | grep "TradingView"

# Direct
tail -f logs/bot.log | grep "TradingView"
```

---

## Support

For issues or questions:
- Check logs: `logs/bot.log`
- Review GitHub issues: https://github.com/vorsoth100/CryptoBot3000/issues
- Ensure all dependencies are installed
- Verify configuration settings are correct

## Security Notice

Both integrations involve sensitive credentials and remote control capabilities:
- Keep bot tokens and webhook secrets secure
- Never commit secrets to version control
- Use environment variables for sensitive data in production
- Monitor access logs regularly
- Consider using a VPN or Tailscale for secure remote access
