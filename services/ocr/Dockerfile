# Use slim Python for smaller image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system deps if needed (e.g., for pillow)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs dir (volume-mounted)
RUN mkdir -p /app/data/logs

# Switch to non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck: Matches docker-compose
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "ocr_service:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]     