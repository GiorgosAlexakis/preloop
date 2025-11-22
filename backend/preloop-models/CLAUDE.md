# SpaceModels Development Guide

## Build & Test Commands
- **Install dependencies**: `pip install -r requirements.txt`
- **Run tests**: `pytest`
- **Run single test**: `pytest tests/path_to_test.py::test_function_name -v`
- **Lint code**: `flake8 .`
- **Type check**: `mypy .`
- **Format code**: `black .`
- **Coverage**: `pytest --cov=spacemodels tests/`

## Style Guidelines
- **Naming**: snake_case for variables/functions, PascalCase for classes
- **Imports**: Sort alphabetically, group standard library, third-party, local imports
- **Formatting**: Use Black with 88 character line length
- **Typing**: Use type hints for function parameters and return values
- **Docstrings**: NumPy or Google style docstrings for classes and functions
- **Error handling**: Use specific exceptions with context messages
- **Testing**: Write tests for all new functionality with pytest

## Git Workflow
- **Branches**: feature/fix/refactor/docs prefixes for branch names
- **Commits**: Clear, concise messages in present tense
- **PRs**: Include test results and brief description of changes