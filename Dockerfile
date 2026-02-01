# Mortar Trading - Docker Build
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files from mortar-trading subdirectory
COPY mortar-trading/pyproject.toml mortar-trading/README.md ./
COPY mortar-trading/mortar_trading ./mortar_trading
COPY mortar-trading/config ./config

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["mortar-web", "--host", "0.0.0.0", "--port", "8000"]
