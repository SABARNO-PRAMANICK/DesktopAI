#!/bin/bash
set -e

echo "🧪 Testing Services..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

TESTS=0
PASSES=0

test_curl() {
    local url=$1
    local desc=$2
    ((TESTS++))
    if curl --fail -s "$url" > /dev/null; then
        echo -e "${GREEN}PASS${NC}: $desc"
        ((PASSES++))
    else
        echo -e "${RED}FAIL${NC}: $desc"
    fi
}

# Health checks
test_curl "http://localhost:11434/api/tags" "Ollama API"
test_curl "http://localhost:8001/health" "OCR Health"
test_curl "http://localhost:8002/health" "STT Health"
test_curl "http://localhost:8003/health" "DB Health"

# Sample endpoints (mock JSON)
test_curl -X POST -H "Content-Type: application/json" -d '{"image_path": "test"}' "http://localhost:8001/process_image" "OCR Process"
test_curl -X POST -H "Content-Type: application/json" -d '{"audio_path": "test"}' "http://localhost:8002/transcribe" "STT Transcribe"
test_curl -X POST -H "Content-Type: application/json" -d '{"json_data": {"action": "test"}}' "http://localhost:8003/store_observation" "DB Store"

echo "Results: $PASSES/$TESTS passed."
if [ $PASSES -eq $TESTS ]; then
    echo "✅ All tests passed!"
else
    echo "⚠️ Some failures—check docker-compose logs."
fi