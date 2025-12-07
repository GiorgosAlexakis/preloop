FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq-dev \
    build-essential \
    curl \
    vim \
    procps \
    iproute2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files first to leverage Docker cache
COPY pyproject.toml .
COPY backend/preloop-models/pyproject.toml backend/preloop-models/
COPY backend/preloop-sync/pyproject.toml backend/preloop-sync/

# Install build dependencies and Python packages in separate layers for better caching
RUN pip install -U --no-cache-dir build setuptools pip wheel ipdb

# Copy only necessary files for preloop-models and preloop-sync installation
COPY backend/preloop-models/ backend/preloop-models/
COPY backend/preloop-sync/ backend/preloop-sync/
RUN pip install --no-cache-dir -e backend/preloop-models && pip install --no-cache-dir -e backend/preloop-sync

# Copy application code (this changes most frequently, so put it last)
COPY backend/preloop-ai/ backend/preloop-ai/
COPY scripts/ scripts/

# Install the main application
RUN pip install --no-cache-dir -e .

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "preloop_ai.server"]
