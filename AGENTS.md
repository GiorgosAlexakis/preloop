# Preloop Development Guide

Only use the DB models defined in the preloop.models package `from preloop.models import models`
Do not access the DB directly in backend code. Always use the CRUD layer at `preloop.models.crud`

Use the Lit.dev framework for frontend code. If you create new web components ensure that the landing page content is not hidden in their shadow DOM.

## Commands
- **Activate venv**: `source .venv/bin/activate || source ../.venv/bin/activate`
- **Install**: `pip install -e ".[dev]"`
- **Run server**: `python -m preloop.server`
- **Run tests**: `pytest`
- **Run single test**: `pytest tests/path/to/test_file.py::TestClass::test_function`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type check**: `mypy backend tests`
- **Docker development**: `docker-compose up`
- **Install pre-commit**: `pre-commit install`
- **PostgreSQL access**: `docker compose exec postgres psql -U postgres -d preloop`
- **Database migrations**: `alembic upgrade head` (from backend/preloop/models)

## Git Workflow

- **NEVER use git push in any form unless explicitly requested by the user**
- After making changes, present them to the user for review before any git operations beyond committing locally
- After making significant changes, consider their impact on README.md and ARCHITECTURE.md and update these files accordingly.

## Code Style
- **Formatting**: Ruff format with 88 character line length
- **Imports**: Use isort with black profile, group stdlib/third-party/local
- **Types**: Use strict typing with mypy, all functions must have type annotations
- **Naming**: snake_case for variables/functions, PascalCase for classes, UPPER_CASE for constants
- **Error handling**: Use specific exceptions, log with appropriate level, handle async errors properly
- **Docstrings**: Google-style with type annotations, document params, returns, raises
- **Async**: Use async for I/O-bound operations, run_async utility for sync contexts
- **Testing**: All code changes should have corresponding tests. Use red/green TDD when possible.

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
5. Activate venv before committing or running pre-commit

## Cursor Cloud specific instructions

The startup update script installs Python deps into `.venv` and frontend deps into `frontend/node_modules`. PostgreSQL 16 (+pgvector), the NATS server binary, and a dev `.env` (gitignored, with a generated `SECRET_KEY`) are baked into the VM snapshot. Services are NOT auto-started — start them each session:

- **PostgreSQL** (port 5432, db `preloop`, user/pass `postgres`/`postgres`): `sudo pg_ctlcluster 16 main start`. Schema + roles are already migrated; re-run `python scripts/init_db.py --force` only after a DB reset.
- **NATS + JetStream** (4222 client, 8222 monitoring): `nats-server -js -m 8222` (run detached, e.g. in tmux).
- **Backend API** (port 8000): from repo root with venv active, `./start.sh`. Health: `curl localhost:8000/api/v1/health`. Swagger at `/docs/api`.
- **Frontend console** (port 5173): `npm run dev` in `frontend/`; Vite proxies `/api` → `127.0.0.1:8000`.
- **Model gateway** (optional, port 8001): same image with `PRELOOP_SERVICE_ROLE=gateway`; only needed for gateway/model-proxy testing.

Gotchas:
- **Do not set `INIT_TEST_DATA=true`** for the running server — the test-data seeder calls `asyncio.run()` inside the live event loop and crashes startup (`./start.sh --init-test-data` triggers this). Leave it `false` and create users via the UI or `POST /api/v1/auth/register` (`username`, `email`, `password`, optional `full_name`; username must be alphanumeric).
- Without `OPENAI_API_KEY`, `init_db.py` skips embedding/AI-model seeding (expected); core auth/console flows still work.
- 3 tests fail under the latest unpinned dependency versions (`backend/tests/test_app.py::test_gateway_role_mounts_only_gateway_surface`, `::test_api_role_excludes_model_gateway_surface`, and `backend/tests/integration/test_flow_execution.py::TestFlowExecution::test_flow_execution_orchestrator`) due to a FastAPI router-internals change (`'_IncludedRouter' object has no attribute 'path'`); ~3065 pass. These are pre-existing and unrelated to environment setup.
