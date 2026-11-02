# API

Tenant identity comes from the access token. Clients do not send `tenant_id`.

Demo password: `queuepilot`.

| Method | Endpoint | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | Public | Access token, role, and email |
| GET | `/api/tenants/me` | Signed in | Current user |
| POST | `/api/jobs` | Tenant | Submit a job. 202, or 200 when the idempotency key repeats |
| GET | `/api/jobs` | Signed in | List. Admin sees every tenant. Filters: `status`, `job_type` |
| GET | `/api/jobs/{id}` | Signed in | Status, result, attempts |
| POST | `/api/jobs/{id}/cancel` | Tenant | Cancel a queued job, or request cancel while it runs |
| GET | `/api/workers` | Admin | Heartbeat, state, current job, utilization |
| GET | `/api/metrics/summary` | Signed in | Counts, last-minute wait, throughput, worker count |
| GET | `/api/metrics/tenants` | Signed in | Per-tenant service and Jain’s index. Tenants see only themselves |
| GET | `/api/admin/scheduler` | Admin | Current policy |
| PATCH | `/api/admin/scheduler` | Admin | `fifo`, `priority`, `wrr`, or `wdrr` |
| GET | `/api/admin/tenants` | Admin | Weights and in-flight limits |
| PATCH | `/api/admin/tenants/{id}` | Admin | Change weight and `max_concurrent_jobs` |
| POST | `/api/admin/benchmarks` | Admin | Start a run. Body: `algorithm`, `seed`, and `preset` or `workload` |
| GET | `/api/admin/benchmarks` | Admin | Recent runs |
| GET | `/api/admin/benchmarks/{id}` | Admin | One run, including metrics when it finishes |
| GET | `/api/admin/scaling` | Admin | Autoscaler events |
| GET | `/health` | Public | PostgreSQL and Redis |

Presets are `fairness`, `priority`, and `unequal_cost`. A custom workload is a list of `{tenant, count, type, params, priority}` with tenants `A`, `B`, or `C`, at most 100 jobs.

Task bodies use `params`:

- `sleep`: `duration_seconds` from 0 to 30
- `hash_compute`: `rounds` from 1 to 100000
- `report_generate`: `title` and `rows` from 1 to 100

`GET /health` returns 200 when both dependencies answer, and 503 otherwise.
