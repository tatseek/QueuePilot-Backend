# Architecture

PostgreSQL holds tenants, jobs, attempts, workers, events, and benchmark rows. The scheduler chooses the next job and reserves it. Redis Streams transport the dispatch message. Workers execute a whitelisted task and write the result back to PostgreSQL.

The scheduler must not copy the whole pending backlog into Redis. Fairness is decided before a job is dispatched.

## Processes

| Process | Role now |
|---|---|
| API | Serves `GET /health` and will own authentication and job routes |
| Scheduler | Starts, checks Postgres and Redis, then waits. Selection is not implemented |
| Worker | Starts, checks Postgres and Redis, then waits. Execution is not implemented |
| Postgres | Source of truth |
| Redis | Dispatch transport, not started until Docker is running |

## Job states

`QUEUED → DISPATCHED → RUNNING → COMPLETED`

Failures move to `RETRY_WAIT` and then back to `QUEUED`, or to terminal `FAILED`. `CANCELLED` is terminal.

## What is stored

`tenants`, `users`, `jobs`, `job_attempts`, `workers`, `job_events`, `outbox_events`, `benchmark_runs`, `scaling_events`.

Demo tenants are Tenant A, Tenant B, and Tenant C with weights 1, 2, and 3.
