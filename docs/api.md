# API

Tenant identity will come from the authenticated token. Clients do not send `tenant_id`.

## Available now

### `POST /api/auth/login`

Body: `email`, `password`. Demo password is `queuepilot`.

### `GET /api/tenants/me`

Current user and tenant. Requires the access token.

### `POST /api/jobs`

Returns 202. Body uses `type`, `priority`, and `params`. Types: `sleep`, `hash_compute`, `report_generate`.

### `GET /api/jobs` and `GET /api/jobs/{id}`

Tenant users only see their own jobs.

### `POST /api/jobs/{id}/cancel`

Queued jobs become `CANCELLED`. Running jobs set a cooperative cancel flag.

### `GET /api/admin/scheduler` and `PATCH /api/admin/scheduler`

Admin only. Policy is `fifo`, `priority`, `wrr`, or `wdrr`. The change applies to later dispatches.

### `GET /health`

Returns 200 when PostgreSQL and Redis both respond.

```json
{"status": "ok", "database": "ok", "redis": "ok"}
```

Returns 503 when either dependency is down. The body uses `"unavailable"` and marks the failed dependency as `"error"`.

## Planned

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Access token |
| GET | `/api/tenants/me` | Current tenant |
| POST | `/api/jobs` | Submit a job, returns 202 |
| GET | `/api/jobs` | Jobs for the current tenant |
| GET | `/api/jobs/{id}` | Status, result, and attempts |
| POST | `/api/jobs/{id}/cancel` | Request cancellation |
| GET | `/api/workers` | Admin worker list |
| GET | `/api/metrics/summary` | Overview counters |
| GET | `/api/metrics/tenants` | Tenant statistics |
| GET | `/api/admin/scheduler` | Current policy |
| PATCH | `/api/admin/scheduler` | Change the policy for later dispatches |
| POST | `/api/admin/benchmarks` | Start a reproducible experiment |
| GET | `/api/admin/benchmarks/{id}` | Benchmark progress and results |

Allowed task types will be `sleep`, `hash_compute`, and `report_generate`.
