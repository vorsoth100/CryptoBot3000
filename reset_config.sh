#!/bin/bash
# Reset configuration to latest defaults

echo "Resetting CryptoBot configuration..."

# Backup old config if it exists
if [ -f "data/config.json" ]; then
    echo "Backing up old config to data/config.json.backup"
    cp data/config.json data/config.json.backup
    rm data/config.json
    echo "✓ Old config removed"
else
    echo "No existing config found"
fi

echo "✓ Configuration will be regenerated with latest defaults on next bot start"
echo ""
echo "New defaults include:"
echo "  - 25 coins monitored (was 9)"
echo "  - Semi-autonomous mode enabled"
echo "  - Analysis runs twice daily"
echo "  - Momentum-focused trading strategy"
echo ""
echo "Please restart the bot to apply changes."
