# CryptoBot3000 - Deployment Guide for Raspberry Pi 5

## 🎯 Deployment Overview

This guide will walk you through deploying CryptoBot3000 to your Raspberry Pi 5 using Portainer.

## ✅ Prerequisites

- Raspberry Pi 5 with Raspberry Pi OS
- Docker installed on Pi
- Portainer installed and running
- Your API keys ready:
  - Coinbase Advanced Trade API Key & Secret
  - Anthropic Claude API Key

## 📦 Step 1: Clone Repository on Raspberry Pi

```bash
# SSH into your Raspberry Pi
ssh pi@<your-pi-ip-address>

# Navigate to home directory
cd ~

# Clone the repository
git clone https://github.com/YOUR_USERNAME/CryptoBot3000.git

# Enter directory
cd CryptoBot3000
```

## 🔑 Step 2: Configure API Keys

```bash
# Copy example env file
cp .env.example .env

# Edit with your actual API keys
nano .env
```

Add your real keys:
```env
COINBASE_API_KEY=your_actual_coinbase_key
COINBASE_API_SECRET=your_actual_coinbase_secret
ANTHROPIC_API_KEY=your_actual_anthropic_key
```

Save (Ctrl+O, Enter, Ctrl+X)

## 🐳 Step 3: Build Docker Image

```bash
# Build the image (this takes 5-10 minutes on Pi 5)
docker build -t cryptobot:latest .

# Verify image was created
docker images | grep cryptobot
```

You should see:
```
cryptobot    latest    <image-id>    <time>    <size>
```

## 📁 Step 4: Create Persistent Volumes

```bash
# Create directories for logs and data
mkdir -p ~/cryptobot-data/logs
mkdir -p ~/cryptobot-data/data

# Set permissions
chmod 755 ~/cryptobot-data/logs
chmod 755 ~/cryptobot-data/data
```

## 🚀 Step 5: Deploy via Portainer

### Option A: Deploy via Portainer Stack (Recommended)

1. Open Portainer in your browser: `http://<pi-ip>:9000`

2. Navigate to **Stacks** > **Add Stack**

3. Fill in details:
   - **Name**: `cryptobot`
   - **Build method**: Web editor

4. Paste this YAML (update paths):
```yaml
version: '3.8'

services:
  cryptobot:
    image: cryptobot:latest
    container_name: cryptobot
    restart: unless-stopped
    ports:
      - "8779:8779"
    volumes:
      - /home/pi/cryptobot-data/logs:/app/logs
      - /home/pi/cryptobot-data/data:/app/data
    environment:
      - COINBASE_API_KEY=${COINBASE_API_KEY}
      - COINBASE_API_SECRET=${COINBASE_API_SECRET}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    env_file:
      - /home/pi/CryptoBot3000/.env
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8779/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

5. Click **Deploy the stack**

### Option B: Deploy via Docker Command (Alternative)

```bash
docker run -d \
  --name cryptobot \
  --restart unless-stopped \
  -p 8779:8779 \
  -v ~/cryptobot-data/logs:/app/logs \
  -v ~/cryptobot-data/data:/app/data \
  --env-file .env \
  cryptobot:latest
```

## 🌐 Step 6: Access the Dashboard

Open your browser and navigate to:
```
http://<raspberry-pi-ip>:8779
```

Example: `http://192.168.1.100:8779`

You should see the CryptoBot dashboard!

## 🧪 Step 7: Test Configuration

1. Click the **Debug** tab

2. Click **Test Coinbase API**
   - Should show: ✓ Connection successful with your balance

3. Click **Test Claude API**
   - Should show: ✓ Claude API configured

4. If both tests pass, you're ready to go!

## ⚙️ Step 8: Configure Bot Settings

1. Go to **Configuration** tab

2. Click **Conservative** preset (recommended for first run)

3. Verify settings:
   - **Dry Run**: ✅ ENABLED (for testing)
   - **Initial Capital**: $600 (or your amount)
   - **Max Positions**: 2
   - **Stop Loss**: 7%
   - **Claude Mode**: Advisory

4. Click **Save Configuration**

## ▶️ Step 9: Start the Bot

1. Go back to **Dashboard** tab

2. Click **Start Bot**

3. Status should change to: 🟢 Running

4. Monitor the dashboard for activity

## 📊 Step 10: Monitor Performance

### Check Logs
```bash
# On Raspberry Pi
docker logs -f cryptobot

# Or in dashboard: Debug tab > Refresh Logs
```

### Check Container Health
```bash
docker ps
# Should show cryptobot with "healthy" status
```

### View in Portainer
- Go to **Containers**
- Click **cryptobot**
- View logs, stats, and health

## 🔄 Updating the Bot

```bash
# Pull latest code
cd ~/CryptoBot3000
git pull

# Rebuild image
docker build -t cryptobot:latest .

# Restart container (in Portainer or via command)
docker restart cryptobot

# Or redeploy stack in Portainer
```

## 🛑 Stopping the Bot

### Via Dashboard:
- Click **Stop Bot** button

### Via Docker:
```bash
docker stop cryptobot
```

### Via Portainer:
- Containers > cryptobot > Stop

## 📱 Port Forwarding (Optional)

To access dashboard from outside your network:

1. **Router Configuration:**
   - Forward port 8779 to your Pi's IP
   - Use a strong authentication method

2. **Security Warning:**
   - ⚠️ Don't expose to public internet without authentication
   - Consider using VPN or Tailscale instead

## 🔒 Security Best Practices

1. **Keep API Keys Secure**
   - Never commit `.env` to Git
   - Use Portainer secrets in production

2. **Start with Dry Run**
   - Test for 7-30 days before live trading
   - Verify all features work correctly

3. **Use Conservative Settings Initially**
   - Start with small capital
   - Monitor first 5-10 trades closely

4. **Regular Monitoring**
   - Check dashboard daily
   - Review Claude analysis
   - Monitor for errors in logs

## 📊 Performance Monitoring

Access these metrics in the dashboard:

- **Dashboard Tab**: Current positions, recent trades
- **Performance Tab**: Win rate, profit factor, total P&L
- **Claude AI Tab**: Market analysis and recommendations
- **Trades Tab**: Complete trade history

## ❓ Troubleshooting

### Container won't start
```bash
# Check logs
docker logs cryptobot

# Verify API keys
cat .env

# Rebuild image
docker build -t cryptobot:latest .
```

### Can't access dashboard
```bash
# Check if container is running
docker ps | grep cryptobot

# Check port
netstat -tuln | grep 8779

# Check firewall
sudo ufw status
sudo ufw allow 8779/tcp
```

### API connection fails
- Verify API keys are correct in `.env`
- Check Coinbase API permissions (View + Trade)
- Ensure internet connection is stable

### High CPU/Memory usage
```bash
# Check resources
docker stats cryptobot

# May need to adjust check_interval_sec in config
```

## 📈 Going Live Checklist

Before switching to live trading (dry_run: false):

- [ ] Successfully run in dry-run for 7+ days
- [ ] Verified all trades execute correctly
- [ ] Checked fee calculations are accurate
- [ ] Tested stop loss triggering
- [ ] Reviewed Claude analysis quality
- [ ] Started with small capital ($50-100)
- [ ] Set up monitoring/alerts
- [ ] Understand all risks

## 🆘 Emergency Stops

### Quick Stop All Trading:
1. Dashboard > Stop Bot
2. OR: `docker stop cryptobot`

### Close All Positions Manually:
1. Dashboard > Each position > Close button
2. Confirm each closure

### Emergency Access to Container:
```bash
# Access container shell
docker exec -it cryptobot bash

# View live logs
tail -f /app/logs/bot.log
```

## 📧 Support

- **GitHub Issues**: Report bugs on GitHub
- **Logs**: Check `/app/logs/bot.log` in container
- **Documentation**: See README.md for full docs

---

## 🎉 You're All Set!

Your CryptoBot3000 is now deployed and running on your Raspberry Pi 5!

**Remember:**
- Start in dry-run mode
- Monitor regularly
- Only trade what you can afford to lose
- Crypto trading is risky

**Good luck and happy trading! 🚀**
