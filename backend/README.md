# Polybot API

Backend of Polybot: FastAPI, a modular monolith, `domain → application → ports → adapters`
(`docs/architecture.md`).

## Commands

Run from `backend/`:

| What | Command |
|---|---|
| Install dependencies | `uv sync` |
| Development server | `uv run uvicorn app.main:app --reload` → http://localhost:8000 |
| Tests | `uv run pytest` |
| Format and lint | `uv run ruff format` · `uv run ruff check` |
| Create a migration | `uv run alembic revision --autogenerate -m "<message>"` |
| Apply migrations | `uv run alembic upgrade head` |
| Seed the example data | `uv run python -m app.adapters.db.seed` |

The API listens on `/api/v1`. Interactive docs: http://localhost:8000/docs.
