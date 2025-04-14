#!/bin/bash
# Start SpaceBridge REST API server

set -e

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
