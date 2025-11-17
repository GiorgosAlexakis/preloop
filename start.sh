#!/bin/bash
# Start SpaceBridge REST API server

set -e

# Load .env file if it exists and variables are not already set
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
  echo "Loading environment variables from $ENV_FILE"
  # Read line by line, ignore comments and empty lines
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Remove comments and leading/trailing whitespace
    line=$(echo "$line" | sed 's/#.*//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # Skip empty lines
    if [ -z "$line" ]; then
      continue
    fi
    # Remove potential 'export ' prefix
    line=$(echo "$line" | sed 's/^export //')
    # Split KEY=VALUE, handle values with '='
    KEY=$(echo "$line" | cut -d '=' -f 1)
    VALUE=$(echo "$line" | cut -d '=' -f 2-)
    # Check if variable is already set in the environment
    # Using indirect expansion: ${!KEY}
    # The condition [ -z "${!KEY}" ] checks if the variable named by KEY is unset or empty.
    if [ -z "${!KEY}" ]; then
      # Export if not set
      export "$KEY=$VALUE"
      # echo "Exported $KEY from $ENV_FILE" # Optional: uncomment for debugging
    # else
      # echo "Skipping $KEY, already set in environment" # Optional: uncomment for debugging
    fi
  done < "$ENV_FILE"
else
  echo "Warning: $ENV_FILE not found. Skipping."
fi
echo "" # Add a blank line for separation
# Initialize database tables, embedding model, and AI model using Alembic
echo "Initializing database schema, embedding model, and AI model..."
python SpaceModels/scripts/init_db.py --force
# Default parameters
API_PORT=8000
DEBUG="true"
INIT_TEST_DATA="false"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      API_PORT="$2"
      shift 2
      ;;
    --debug)
      DEBUG="true"
      shift
      ;;
    --init-test-data)
      INIT_TEST_DATA="true"
      shift
      ;;
    --help)
      echo "SpaceBridge Startup Script"
      echo ""
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --port PORT          Port for the REST API server (default: 8000)"
      echo "  --debug              Enable debug mode"
      echo "  --init-test-data     Initialize test data on startup"
      echo "  --help               Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Set environment variables
export DEBUG="$DEBUG"
export INIT_TEST_DATA="$INIT_TEST_DATA"
export PORT="$API_PORT"

# Function to stop the process when the script exits
function cleanup {
  echo "Stopping service..."
  if [ -n "$API_PID" ]; then
    kill $API_PID 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Debug and test data flags
debug_flag=""
test_data_flag=""
if [ "$DEBUG" = "true" ]; then
  debug_flag="--debug"
fi
if [ "$INIT_TEST_DATA" = "true" ]; then
  test_data_flag="--init-test-data"
fi

# Build MkDocs documentation if mkdocs is available
if command -v mkdocs &> /dev/null; then
    echo "Building documentation with MkDocs..."
    mkdocs build
    echo "Documentation build complete."
else
    echo "Warning: 'mkdocs' command not found. Skipping documentation build."
    echo "         Install docs dependencies with: pip install -e '.[dev]'"
fi

echo ""
echo "Starting SpaceBridge REST API with configuration:"
echo " - API Server: http://localhost:$API_PORT"
echo " - API Documentation (Swagger): http://localhost:$API_PORT/docs/api"
echo " - User Documentation: http://localhost:$API_PORT/docs"
echo " - Debug mode: $DEBUG"
echo " - Init test data: $INIT_TEST_DATA"

# Start the API server in the foreground
python -m spacebridge.server --port "$API_PORT" $debug_flag $test_data_flag
