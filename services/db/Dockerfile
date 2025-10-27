# Use slim Python for smallest image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# No system deps needed for SQLite

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs and migrations dirs (volumes for data)
RUN mkdir -p /app/data/logs /app/migrations

# Switch to non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Healthcheck: Query DB to ensure tables exist
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "from sqlalchemy import create_engine; engine = create_engine('sqlite:////app/data/agi_assistant.db'); with engine.connect() as conn: conn.execute('SELECT COUNT(*) FROM observations').fetchone()" || exit 1

# Run the application
CMD ["uvicorn", "db_service:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]