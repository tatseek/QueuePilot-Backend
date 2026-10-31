# QueuePilot Backend

Multi-tenant job API, scheduler, and workers. PostgreSQL is the source of truth. Redis Streams carry dispatch messages. This repository is the foundation milestone: schema, health check, and demo tenants.

Credentials in `.env.example` and `docker-compose.yml` are for this local database only.

The dashboard lives in the separate frontend repository.

## Requirements

- Docker Desktop with WSL2
- Python 3.12+

## Start locally

From this directory:

```powershell
docker compose up -d postgres redis
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.services.seed
docker compose up -d api
```

Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Scheduler and worker processes stay idle until dispatch is implemented. Start them with the API when you want the full process list:

```powershell
docker compose up -d api scheduler worker
```

## Host-side API

With Postgres and Redis already published on localhost:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
py scripts\seed_demo.py
uvicorn app.main:app --reload --port 8000
```

## Tests

```powershell
python -m pytest
```

## Docs

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Experiments](docs/experiments.md)
