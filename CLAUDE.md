# SpaceBridge Development Guide

## Commands
- **Install**: `pip install -e ".[dev]"`
- **Run server**: `python -m spacebridge.server`
- **Run tests**: `pytest`
- **Run single test**: `pytest tests/path/to/test_file.py::TestClass::test_function`
- **Lint**: `black . && isort . && ruff check .`
- **Type check**: `mypy spacebridge tests`
- **Docker development**: `docker-compose up`

## Code Style
- **Formatting**: Black with 88 character line length
- **Imports**: Use isort with black profile, group stdlib/third-party/local
- **Types**: Use strict typing with mypy, all functions must have type annotations
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- **Error handling**: Use specific exceptions, log with appropriate level, handle async errors properly
- **Docstrings**: Google-style with type annotations, document params, returns, raises
- **Async**: Use async for I/O-bound operations, run_async utility for sync contexts
- **Testing**: All code changes should have corresponding tests