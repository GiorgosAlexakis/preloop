#\!/bin/bash
source .venv/bin/activate
PYTHONPATH=$PYTHONPATH:. python -m pytest "$@"
