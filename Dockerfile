# Stage 1: Build SpaceLit
FROM node:18-alpine AS space-lit-build
WORKDIR /app
COPY SpaceLit /app
RUN npm install && npm run build

# Stage 2: Build SpaceBridge
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including PostgreSQL client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files first to leverage Docker cache
COPY pyproject.toml .
COPY SpaceModels/pyproject.toml SpaceModels/
COPY spacesync/setup.py spacesync/
COPY spacesync/requirements.txt spacesync/

# Install build dependencies and Python packages in separate layers for better caching
RUN pip install -U --no-cache-dir build setuptools pip wheel mkdocs mkdocs-material mkdocs-mermaid2-plugin

# Copy only necessary files for SpaceModels and spacesync installation
COPY SpaceModels/ SpaceModels/
COPY spacesync/ spacesync/
RUN pip install --no-cache-dir -e SpaceModels && pip install --no-cache-dir -e spacesync

# Copy application code (this changes most frequently, so put it last)
COPY spacebridge/ spacebridge/
COPY static/ static/
COPY docs/ docs/
COPY mkdocs.yml .

# Copy built frontend assets
COPY --from=space-lit-build /app/dist /app/SpaceLit/dist

# Install the main application and build docs
RUN pip install --no-cache-dir -e . && mkdocs build

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "spacebridge.server"]
