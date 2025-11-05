FROM python:3.12-slim

WORKDIR /app

# Install dependencies
# Note: fastapi needs to be explicitly installed even though fastmcp depends on it
RUN pip install --no-cache-dir fastmcp fastapi uvicorn

# Copy the example MCP server
COPY example_mcp_server.py .

# Expose port
EXPOSE 8001

# Set default bearer token (should be overridden via env var)
ENV BEARER_TOKEN=default-test-token

# Run the server
CMD ["python", "example_mcp_server.py"]
