# Extend official Ollama with curl for healthcheck
FROM ollama/ollama:latest

# Install curl (Ubuntu/Debian package manager)
USER root
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Stay as root (official image default—no 'ollama' user exists)
# No USER ollama

# Expose port (inherited)
EXPOSE 11434

# Healthcheck (now curl exists)
HEALTHCHECK --interval=20s --timeout=30s --start-period=60s --retries=5 \
  CMD curl -f http://localhost:11434/api/version || exit 1