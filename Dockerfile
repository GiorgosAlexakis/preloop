FROM python:3.10-slim

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY pyproject.toml .

# Install build dependencies
RUN pip install --no-cache-dir build setuptools wheel

# Copy application code
COPY . .

# Install the application
RUN pip install --no-cache-dir -e .

# Expose the port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "spacebridge.server"]
