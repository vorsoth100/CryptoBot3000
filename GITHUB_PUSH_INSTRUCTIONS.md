# GitHub Push Instructions

## ✅ Status: Ready to Push

Your CryptoBot3000 project is complete and committed locally. Follow these steps to push to GitHub.

## 📋 Steps to Push to GitHub

### 1. Create a New Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `CryptoBot3000` (or your preferred name)
3. Description: "AI-Powered Cryptocurrency Trading Bot with Claude AI and Coinbase Integration"
4. Choose: **Private** (recommended - contains trading code)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click **Create repository**

### 2. Add GitHub Remote

Copy the repository URL from GitHub, then run:

```bash
# SSH (recommended if you have SSH keys set up)
git remote add origin git@github.com:YOUR_USERNAME/CryptoBot3000.git

# OR HTTPS (easier for first-time)
git remote add origin https://github.com/YOUR_USERNAME/CryptoBot3000.git
```

Replace `YOUR_USERNAME` with your GitHub username.

### 3. Push to GitHub

```bash
# Rename branch to 'main' (GitHub's default)
git branch -M main

# Push all files
git push -u origin main
```

### 4. Verify Push

Go to your GitHub repository URL and verify all files are there:
- ✅ src/ directory with 10 Python files
- ✅ web/ directory with dashboard
- ✅ Docker files
- ✅ README.md
- ✅ requirements.txt

## 🔒 Security Check

Before pushing, verify `.gitignore` is protecting sensitive files:

```bash
# This should show that .env is ignored
git status
```

The following should **NOT** be in the repo:
- ❌ `.env` file (contains API keys)
- ❌ `logs/` directory
- ❌ `data/config.json` (may contain settings)

Only `.env.example` should be included (with placeholder values).

## 📝 Post-Push: Update Repository Settings

1. Go to your repo on GitHub
2. Click **Settings** > **General**
3. Add topics/tags: `cryptocurrency`, `trading-bot`, `claude-ai`, `coinbase`, `python`, `docker`
4. Add description and website (if you have one)

### Optional: Add Repository Secrets (for CI/CD later)

If you plan to use GitHub Actions:
1. Go to **Settings** > **Secrets and variables** > **Actions**
2. Add secrets (do not commit these anywhere):
   - `COINBASE_API_KEY`
   - `COINBASE_API_SECRET`
   - `ANTHROPIC_API_KEY`

## 🚀 Next: Deploy to Raspberry Pi 5

After pushing to GitHub, you can clone on your Raspberry Pi:

```bash
# On Raspberry Pi 5
cd ~
git clone https://github.com/YOUR_USERNAME/CryptoBot3000.git
cd CryptoBot3000

# Create .env file with your API keys
cp .env.example .env
nano .env  # Add your real API keys

# Build Docker image
docker build -t cryptobot:latest .

# Deploy via Portainer
# - Open Portainer web interface
# - Stacks > Add Stack
# - Paste content from portainer-stack.yml
# - Update paths and deploy
```

## 🔗 Quick Commands Summary

```bash
# 1. Add remote (use YOUR username)
git remote add origin https://github.com/YOUR_USERNAME/CryptoBot3000.git

# 2. Rename branch and push
git branch -M main
git push -u origin main

# 3. Verify
git remote -v
```

## ❓ Troubleshooting

### Error: "remote origin already exists"
```bash
git remote remove origin
# Then try adding again
```

### Error: "failed to push some refs"
```bash
git pull origin main --rebase
git push -u origin main
```

### Error: "Authentication failed"
- For HTTPS: Use a Personal Access Token instead of password
  - Generate at: https://github.com/settings/tokens
- For SSH: Set up SSH keys
  - Guide: https://docs.github.com/en/authentication/connecting-to-github-with-ssh

## 📧 Support

If you encounter issues:
1. Check GitHub's push documentation
2. Verify your GitHub credentials
3. Ensure you have write access to the repository

---

**You're all set! Once pushed, you can deploy to your Raspberry Pi 5!** 🎉
