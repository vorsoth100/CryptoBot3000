#!/bin/bash

# CryptoBot3000 - GitHub Push Script
# This script helps you push your code to GitHub

echo "=========================================="
echo "CryptoBot3000 - GitHub Push Helper"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "Error: Please run this script from the CryptoBot3000 directory"
    exit 1
fi

# Prompt for GitHub username
read -p "Enter your GitHub username: " GITHUB_USERNAME

if [ -z "$GITHUB_USERNAME" ]; then
    echo "Error: GitHub username cannot be empty"
    exit 1
fi

# Prompt for repository name
read -p "Enter repository name [CryptoBot3000]: " REPO_NAME
REPO_NAME=${REPO_NAME:-CryptoBot3000}

echo ""
echo "=========================================="
echo "Repository will be:"
echo "https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo "=========================================="
echo ""

# Ask for confirmation
read -p "Is this correct? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Step 1: Please create the repository on GitHub"
echo "=========================================="
echo "1. Go to: https://github.com/new"
echo "2. Repository name: $REPO_NAME"
echo "3. Description: AI-Powered Cryptocurrency Trading Bot with Claude AI"
echo "4. Choose: Private (recommended)"
echo "5. DO NOT initialize with README, .gitignore, or license"
echo "6. Click 'Create repository'"
echo ""
read -p "Press Enter once you've created the repository on GitHub..."

echo ""
echo "Step 2: Adding GitHub remote..."
echo "=========================================="

# Check if remote already exists
if git remote get-url origin > /dev/null 2>&1; then
    echo "Remote 'origin' already exists. Removing it..."
    git remote remove origin
fi

# Add remote
git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
echo "✓ Remote added: https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

echo ""
echo "Step 3: Renaming branch to 'main'..."
echo "=========================================="
git branch -M main
echo "✓ Branch renamed to 'main'"

echo ""
echo "Step 4: Pushing to GitHub..."
echo "=========================================="
echo "You may be prompted for GitHub credentials..."
echo ""

# Push to GitHub
if git push -u origin main; then
    echo ""
    echo "=========================================="
    echo "✓ SUCCESS! Code pushed to GitHub!"
    echo "=========================================="
    echo ""
    echo "Your repository is now available at:"
    echo "https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo ""
    echo "Next steps:"
    echo "1. View your repo: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo "2. Follow DEPLOYMENT_GUIDE.md to deploy to Raspberry Pi 5"
    echo "3. Access dashboard at: http://<pi-ip>:8779"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "✗ Push failed"
    echo "=========================================="
    echo ""
    echo "Common issues:"
    echo "1. Authentication failed:"
    echo "   - Use a Personal Access Token instead of password"
    echo "   - Generate at: https://github.com/settings/tokens"
    echo ""
    echo "2. Repository doesn't exist:"
    echo "   - Make sure you created the repo on GitHub first"
    echo "   - Verify the repo name: $REPO_NAME"
    echo ""
    echo "3. Permission denied:"
    echo "   - Check you have write access to the repository"
    echo ""
    echo "To try again, run: ./PUSH_TO_GITHUB.sh"
    exit 1
fi
