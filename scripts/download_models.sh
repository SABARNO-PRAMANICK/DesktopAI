#!/bin/bash
set -e

echo "📥 Downloading Models..."

# OCR Vision Model (~2.5GB, multimodal for edge)
docker exec agi_ollama ollama pull llava:7b || echo "Llava 7b already exists."

# LLM Reasoning: Qwen2.5 7B (~4.4GB, better perf than Phi-3)
docker exec agi_ollama ollama pull qwen2.5:latest || echo "Qwen2.5 7B already exists."

echo "List models:"
docker exec agi_ollama ollama list

echo "✅ Models ready! Total ~6.9GB. Faster inference on edge hardware."