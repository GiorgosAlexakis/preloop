FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY pyproject.toml .

# Install build dependencies
RUN pip install -U --no-cache-dir build setuptools pip wheel mkdocs mkdocs-material mkdocs-mermaid2-plugin

# Copy application code
COPY . .

# Install the application
RUN pip install --no-cache-dir -e SpaceModels && pip install --no-cache-dir -e spacesync && pip install --no-cache-dir -e . && mkdocs build

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "spacebridge.server"]
