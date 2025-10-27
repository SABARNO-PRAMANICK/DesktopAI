#!/bin/bash
set -e  # Exit on error

echo "🚀 AGI Assistant Setup Starting..."

# Create dirs
mkdir -p data logs scripts test_data services/{ocr,stt,db}/{migrations}

# Load env
if [ -f .env ]; then
    source .env
else
    echo "❌ .env not found! Copy .env.example to .env."
    exit 1
fi

# Build & start
echo "Building services..."
docker-compose build --no-cache

echo "Starting services..."
docker-compose up -d

# Wait for health (max 60s)
echo "Waiting for services to be healthy..."
for i in {1..12}; do
    if docker-compose ps | grep -q "healthy"; then
        echo "✅ All services healthy!"
        break
    fi
    sleep 5
done

# Init DB (run migration placeholder)
echo "Initializing DB..."
docker exec agi_db python -c "
from sqlalchemy import create_engine
from models import Base
engine = create_engine('sqlite:///$DB_PATH')
Base.metadata.create_all(engine)
print('DB tables created.')
"

# Log to file
docker-compose logs > logs/setup_$(date +%Y%m%d_%H%M%S).log

echo "✅ Setup complete! Run 'docker-compose ps' to verify."
echo "Next: bash scripts/download_models.sh"