# Contributing to SpaceBridge

Thank you for your interest in contributing to SpaceBridge! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

All contributors are expected to adhere to the project's code of conduct. Please be respectful and constructive in all interactions.

## Getting Started

### Development Environment

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/spacebridge.git`
3. Create a virtual environment: `python -m venv .venv`
4. Activate the virtual environment:
   - Unix/macOS: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
5. Install development dependencies: `pip install -e ".[dev]"`
6. Set up pre-commit hooks: `pre-commit install`

### Database Setup

1. Install PostgreSQL 14+ and the PGVector extension
2. Create a database for development
3. Copy `.env.example` to `.env` and update the database connection string
4. Run `python -m spacemodels.db.setup` to initialize the database schema

## Development Workflow

### Branching Strategy

- `main` branch contains the latest stable release
- `develop` branch is the integration branch for ongoing development
- Feature branches should be created from `develop` and named according to the following convention:
  - `feature/short-description` for new features
  - `bugfix/short-description` for bug fixes
  - `chore/short-description` for maintenance tasks

### Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Where `type` is one of:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools

### Testing

All code changes should be accompanied by appropriate tests. We use pytest for testing:

```bash
python -m pytest
```

To run tests with coverage:

```bash
python -m pytest --cov=spacebridge
```

### Code Style

We use the following tools to maintain code quality:

- `black` for code formatting
- `isort` for import sorting
- `mypy` for static type checking
- `ruff` for linting

You can run all checks with:

```bash
black .
isort .
mypy spacebridge tests
ruff check .
```

## Pull Request Process

1. Ensure your code passes all tests and style checks
2. Update documentation if necessary
3. Create a pull request against the `develop` branch
4. Include a clear description of the changes and any relevant issue numbers
5. Wait for a review from a maintainer

## Documentation

Documentation is a critical part of this project. Please ensure that all new features are properly documented, including:

- Docstrings for all public functions, classes, and methods
- Updates to relevant README and architecture documents
- API documentation for new endpoints or tools

## Questions and Support

If you have questions about contributing, please open an issue labeled "question" in the GitHub repository.

Thank you for contributing to SpaceBridge!
