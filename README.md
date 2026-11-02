# QueuePilot Backend

Multi-tenant job API, scheduler, workers, and a host-side autoscaler. PostgreSQL stores the queue. Redis Streams carry one dispatch message per reserved job.

Credentials in `.env.example` and `docker-compose.yml` are for this local database only. Do not point them at Supabase.

The dashboard lives in the separate frontend repository.

## Requirements

- Python 3.12+
- PostgreSQL and Redis on localhost

On this machine those run as native programs on `D:`, not in Docker. `docker-compose.yml` remains for a computer where Docker already works. Start three workers there with `docker compose up --build -d --scale worker=3` once the image exists. This laptop starts workers as extra Python processes instead.

## Start locally

With PostgreSQL on `127.0.0.1:5432` and Redis on `127.0.0.1:6379`:

```powershell
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m app.services.seed
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python -m app.scheduler.main
.\.venv\Scripts\python -m app.workers.main
.\.venv\Scripts\python -m app.workers.main
.\.venv\Scripts\python -m app.workers.main
```

The last three lines are the three worker replicas. One worker is enough for a smoke test.

Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

Demo logins use password `queuepilot`: `a@queuepilot.local`, `b@queuepilot.local`, `c@queuepilot.local`, and `admin@queuepilot.local`.

Optional autoscaler, from this directory:

```powershell
.\.venv\Scripts\python scripts\autoscaler.py
```

It keeps 1 to 5 healthy workers. A sustained queue above 10 jobs per worker adds one. A sustained queue below 2 drains an idle worker. Changes wait 30 seconds and are written to `scaling_events`.

Optional load test, after `pip install -r requirements.txt`:

```powershell
.\.venv\Scripts\locust -f locustfile.py --host http://127.0.0.1:8000
```

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

Live tests call the local database and skip themselves when it is down.

## Docs

- [Architecture](docs/architecture.md)
- [API](docs/api.md)
- [Experiments](docs/experiments.md)
- [Report notes](docs/report.md)
- [Viva](docs/viva.md)
