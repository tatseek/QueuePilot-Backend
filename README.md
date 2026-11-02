# QueuePilot Backend

Multi-tenant job API, scheduler, and workers. PostgreSQL is the source of truth. Redis Streams carry dispatch messages. This repository is the foundation milestone: schema, health check, and demo tenants.

Credentials in `.env.example` and `docker-compose.yml` are for this local database only.

The dashboard lives in the separate frontend repository.

## Requirements

- Docker Desktop with WSL2
- Python 3.12+

## Start locally

PostgreSQL and Redis run on this machine, with their files on `D:`. From this directory, with both already listening:

```powershell
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app.services.seed
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python -m app.scheduler.main
.\.venv\Scripts\python -m app.workers.main
```

Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Demo logins use password `queuepilot`: `a@queuepilot.local`, `b@queuepilot.local`, `c@queuepilot.local`, and `admin@queuepilot.local`.

`docker-compose.yml` is still here for a machine where Docker already works. It is not required to run the API.

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
