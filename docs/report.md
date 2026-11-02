# QueuePilot report notes

These notes follow the roadmap’s report outline. Measured tables belong in [experiments.md](experiments.md), copied from exported benchmark JSON. Do not invent a winner.

## 1. Introduction

Shared clusters let one tenant’s backlog delay everyone else when the scheduler is plain FIFO. QueuePilot is a local multi-tenant job system: PostgreSQL stores the queue, a scheduler reserves one job at a time, Redis Streams deliver that reservation, and workers run a fixed set of tasks.

## 2. Related work

FIFO serves the oldest job. Priority serves an explicit rank and breaks ties by age. Weighted round robin gives each tenant a number of turns equal to its weight, which is fair when every job costs about the same. Deficit round robin carries unused credit so a tenant with heavier jobs is not starved and a tenant with light jobs is not over-served. The project implements the weighted form (WDRR) with a base quantum of 1. Production queues (for example cloud worker fleets) separate admission, dispatch, and execution the same way, usually with a much larger control plane.

## 3. Requirements

Tenants submit only `sleep`, `hash_compute`, and `report_generate`. Identity comes from the token. Jobs reach a terminal state. Attempts are bounded. Workers can be added and drained on this machine. Scheduling policies can be compared on the same workload.

Out of scope: arbitrary code, a public cloud, Kubernetes, and exactly-once delivery.

## 4. Architecture

See [architecture.md](architecture.md) for the sequence and the tables. The scheduler never publishes a job it has not already reserved. The outbox row and the status change commit together.

## 5. Implementation

FastAPI serves the contract in [api.md](api.md). SQLAlchemy models match the roadmap tables. Alembic migrations `0001_initial` and `0002_scheduler_state` create them. Workers execute tasks in-process and check a cancellation flag between steps. The autoscaler is `scripts/autoscaler.py` on the host. It starts `python -m app.workers.main` or sets a worker to `DRAINING`. The API process does not receive a Docker socket.

## 6. Algorithms

Selection reads the oldest 200 queued jobs of each tenant that is under its in-flight limit. A single global cap would hide a small tenant behind a long backlog. FIFO and priority are sorts. WRR and WDRR walk tenants from a cursor and stop at the first job the current credit can pay for. Each successful reserve is one transaction with `FOR UPDATE SKIP LOCKED` on the chosen row.

## 7. Evaluation

Timestamps `created_at`, `dispatched_at`, `started_at`, and `finished_at` are on the job. Metrics are waiting time, execution, turnaround, throughput, p95 wait, failure rate, and Jain’s index on cost divided by weight. Presets and seeds are stored with the run. The worker count and the machine are part of the conditions; a single laptop run is not a cloud bill.

## 8. Results

The measured tables are in [experiments.md](experiments.md). On the A=1000, B=50, C=10 run, WDRR cut the small tenants’ mean wait from about 109s and 104s to 10.7s and 3.9s, while Tenant A stayed near 106s and throughput stayed near 5.3 jobs per second. Jain’s index did not move, because both runs finished every job. The smaller presets show the same pattern for fairness, the priority reversal, and a case where WDRR lost on throughput. Killing a worker during a 15 second sleep recovered the job on attempt 2 in 46.2 seconds. A 20 second Locust run submitted 225 jobs with no HTTP failures.

## 9. Limitations

One machine, cooperative cancellation, at-least-once stream delivery, and a scheduler interval of half a second all change the waits. Heartbeats and leases are wall-clock based. The benchmark switches the live policy and restores it afterward, so it should be the only writer during a run. The large fairness pair was run once. The scheduler looks at 200 jobs per tenant per pass, not the entire backlog.

## 10. Future work

Repeat the large pair and report the spread. WebSocket updates are optional. The polling dashboard already shows the same data.

## Demo script

1. Start PostgreSQL, Redis, the API, the scheduler, and three workers.
2. Log in as admin and show the three tenants.
3. Submit work as Tenant A, then a few jobs as Tenant B.
4. Run the fairness preset under FIFO, then under WDRR, and export both.
5. Start `scripts/autoscaler.py`, queue a burst, and show a scaling event.
6. Stop one worker during a sleep job and show the job finish on another attempt.
