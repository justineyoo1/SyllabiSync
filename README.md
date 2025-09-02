# SyllabusSync (Scaffold)

Minimal scaffold for a RAG-ready syllabus assistant.

## Requirements
- Python 3.11+
- Docker + Docker Compose

## Setup

1. Create and populate `.env` from example:
```bash
cp .env.example .env
```

2. Install Python deps (optional if running via Docker only):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Start services:
```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

4. API available at:
- http://localhost:8000
- OpenAPI: http://localhost:8000/docs

5. Alembic migrations:
```bash
alembic revision -m "init"
alembic upgrade head
```

## Repo Layout
```
apps/
  api/
    routers/  # FastAPI endpoints
    deps/     # DI providers (db, redis, s3)
    schemas/  # Pydantic models
    services/ # Business logic
  worker/
    jobs/     # Celery tasks
packages/
  common/     # config, logging
  parsers/
  rag/
infra/
  docker/     # docker-compose, Dockerfiles
alembic/
```

## Development
- Lint: `ruff check .`
- Format: `black .`
- Types: `mypy .`
- Test: `pytest`

## Conventional Commits
Use conventional commits (e.g., `feat:`, `fix:`, `chore:`) for consistency.
