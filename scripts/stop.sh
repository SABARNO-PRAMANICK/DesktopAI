#!/bin/bash
set -e

echo "⏹️ Stopping Services..."

# Backup DB
if [ -f data/agi_assistant.db ]; then
    cp data/agi_assistant.db "data/backup_$(date +%Y%m%d_%H%M%S).db"
    echo "DB backed up."
fi

docker-compose down
echo "✅ Stopped. Data preserved in ./data/."