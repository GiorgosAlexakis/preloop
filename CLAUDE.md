# SpaceBridge Development Guide

Only use the DB models defined in SpaceModels package `from spacemodels import models`

Use the Lit.dev framework for frontend code. If you create new web components ensure that the landing page content is not hidden in their shadow DOM.

## Commands
- **Install**: `pip install -e ".[dev]"`
- **Run server**: `python -m spacebridge.server`
- **Run tests**: `pytest`
- **Run single test**: `pytest tests/path/to/test_file.py::TestClass::test_function`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type check**: `mypy spacebridge tests`
- **Docker development**: `docker-compose up`
- **Install pre-commit**: `pre-commit install`

## Commit message Guidelines

- All commit messages should include references to relevant issues in the tracker. Use the SpaceBridge-MCP tools to find or create issues for every change. Include the issue key in the commit message footer. Ensure issue title and description are clear and concise, always in present tense.


## Code Style
- **Formatting**: Ruff format with 88 character line length
- **Imports**: Use isort with black profile, group stdlib/third-party/local
- **Types**: Use strict typing with mypy, all functions must have type annotations
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- **Error handling**: Use specific exceptions, log with appropriate level, handle async errors properly
- **Docstrings**: Google-style with type annotations, document params, returns, raises
- **Async**: Use async for I/O-bound operations, run_async utility for sync contexts
- **Testing**: All code changes should have corresponding tests

## Pre-commit Hooks
The project uses pre-commit hooks to ensure code quality. These hooks run automatically before each commit and include:
- Code formatting with ruff format
- Import sorting with isort
- Linting with ruff
- Various file checks (trailing whitespace, YAML validity, etc.)

To use pre-commit:
1. Install pre-commit: `pip install pre-commit`
2. Install the hooks: `pre-commit install`
3. The hooks will run automatically on git commit
4. To run hooks manually: `pre-commit run --all-files`
