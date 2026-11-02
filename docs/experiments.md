# Experiments

Runs come from `POST /api/admin/benchmarks` on this machine. Three healthy workers, seed 1, grouped arrival, `hash_compute` at 1000 rounds. Numbers are copied from the stored metrics, not estimated. `scripts/run_study.py` repeats the large fairness pair.

Jain’s index uses completed cost divided by weight. When every job in the preset finishes, that index does not change between algorithms, because the completed cost is the same. Waiting time is what changes. Both are reported.

## Fairness study

3 November 2026. A=1000, B=50, C=10. The scheduler considers the oldest 200 queued jobs of each tenant, so B and C stay visible behind A’s backlog. Every job finished. Jain’s index is 0.352 for both algorithms because the completed cost is the same; the difference is who waited.

| Algorithm | Mean wait | P95 wait | Tenant A | Tenant B | Tenant C | Throughput |
|---|---:|---:|---:|---:|---:|---:|
| fifo | 103.7s | 194.7s | 103.4s | 109.0s | 103.9s | 5.18/s |
| wdrr | 100.8s | 188.4s | 106.3s | 10.7s | 3.9s | 5.35/s |

WDRR left Tenant A about the same (106.3s against 103.4s) and cut Tenant B from 109.0s to 10.7s and Tenant C from 103.9s to 3.9s. Overall mean and throughput barely moved. This is one pair on one laptop, not a repeated trial.

## Fairness preset

A=8, B=4, C=2, equal cost.

| Run | Algorithm | Mean wait | P95 wait | Tenant A | Tenant B | Tenant C | Jain |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | fifo | 3.36s | 4.52s | 3.57s | 3.31s | 2.63s | 0.554 |
| 2 | wdrr | 1.27s | 2.41s | 1.61s | 0.81s | 0.82s | 0.554 |
| 3 | fifo | 1.40s | 2.54s | 1.54s | 1.21s | 1.21s | 0.554 |

Run 1 was the first pass while the workers had just started, so its waits are higher. Runs 2 and 3 are the matched pair. WDRR cut Tenant B and Tenant C mean wait (0.81s and 0.82s against 1.21s and 1.21s under FIFO) and Tenant A waited a little longer (1.61s against 1.54s). One pair is not a stable ranking. Repeat it before treating WDRR as faster overall: run 3’s FIFO p95 (2.54s) is close to WDRR’s (2.41s).

## Priority preset

Six jobs at priority 1, then four at priority 8, all Tenant A.

| Algorithm | Mean wait, priority 1 | Mean wait, priority 8 | P95 |
|---|---:|---:|---:|
| fifo | 0.41s | 1.12s | 1.41s |
| priority | 1.15s | 0.31s | 1.52s |

FIFO served the jobs in submit order, so the later high-priority jobs waited longer. The priority policy reversed that: priority 8 mean wait 0.31s, priority 1 mean wait 1.15s. Throughput stayed in the same range (about 6 and 5.7 completed jobs per second).

## Unequal cost preset

Tenant A, four jobs of cost 1. Tenant B, four jobs of cost 8.

| Algorithm | Tenant A mean wait | Tenant B mean wait | P95 | Throughput |
|---|---:|---:|---:|---:|
| wrr | 0.99s | 0.58s | 1.39s | 5.73/s |
| wdrr | 0.54s | 3.26s | 5.04s | 1.43/s |

WDRR gave the light tenant a shorter wait and held the heavy tenant back, and throughput dropped on this run. Jain stayed 0.735 for both, again because both runs finished every job. This is a case where WDRR did not win on throughput or on the heavy tenant’s wait.

## Scaling and failure

The decision rule is covered by unit tests: scale up after three samples above 10 queued jobs per healthy worker, scale down after three samples below 2, never below the minimum of 1 or above 5, with a 30 second cooldown.

On this machine, with one healthy worker held on a 25 second sleep and 15 hash jobs waiting, `scripts/autoscaler.py` recorded `1 → 2` at 15:17 with the reason “queued jobs per worker stayed above the threshold”. Earlier idle samples recorded scale-down events (`3 → 2`, `2 → 1`). The autoscaler was then stopped so it would not keep changing the worker count.

Workers refresh their heartbeat while a task is running, so a long sleep is not mistaken for a dead process. If heartbeats do stop, an expired lease returns the job to `RETRY_WAIT` or `FAILED`. A redelivered stream entry whose attempt id is no longer current is acknowledged and not written as the result.

On 3 November 2026 a 15 second sleep was killed while `RUNNING`. The job reached `COMPLETED` on attempt 2, 46.2 seconds after the process was stopped. That interval is the remaining 30 second lease plus the second execution. The first attempt did not stay as the result.

## Load

`locustfile.py`, Locust 2.32.9, 3 November 2026, 8 users, spawn rate 2, 20 seconds, against the API on this machine with three workers:

| Request | Count | Failures | Median | P95 |
|---|---:|---:|---:|---:|
| POST `/api/jobs` | 225 | 0 | 7 ms | 12 ms |
| POST `/api/auth/login` | 8 | 0 | 74 ms | 80 ms |

All 225 hash jobs later completed. Their queue wait, measured from `started_at - created_at`, had mean 10.6s and p95 21.1s. Submit rate was about 12 requests per second, ahead of three workers, which is why the wait is seconds rather than milliseconds.
