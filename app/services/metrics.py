from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import Job, JobStatus, Tenant, Worker

TERMINAL = {
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def jain_index(allocations: list[float]) -> float | None:
    if not allocations:
        return None
    squares = sum(value * value for value in allocations)
    if squares == 0:
        return None
    total = sum(allocations)
    return (total * total) / (len(allocations) * squares)


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _seconds(later: datetime | None, earlier: datetime | None) -> float | None:
    if later is None or earlier is None:
        return None
    return (later - earlier).total_seconds()


def summarize_jobs(
    jobs: list[Job],
    weights: dict[UUID, tuple[str, int]],
    elapsed_seconds: float | None,
) -> dict:
    waits: list[float] = []
    executions: list[float] = []
    turnarounds: list[float] = []
    by_tenant: dict[UUID, dict] = {}
    by_priority: dict[int, list[float]] = {}
    for job in jobs:
        name, weight = weights.get(job.tenant_id, (str(job.tenant_id), 1))
        bucket = by_tenant.setdefault(
            job.tenant_id,
            {
                "tenant_id": str(job.tenant_id),
                "name": name,
                "weight": weight,
                "completed": 0,
                "failed": 0,
                "service": 0,
                "waits": [],
            },
        )
        if job.status == JobStatus.COMPLETED.value:
            bucket["completed"] += 1
            bucket["service"] += job.estimated_cost
        elif job.status == JobStatus.FAILED.value:
            bucket["failed"] += 1
        wait = _seconds(job.started_at, job.created_at)
        if wait is not None:
            waits.append(wait)
            bucket["waits"].append(wait)
            by_priority.setdefault(job.priority, []).append(wait)
        execution = _seconds(job.finished_at, job.started_at)
        if execution is not None:
            executions.append(execution)
        turnaround = _seconds(job.finished_at, job.created_at)
        if turnaround is not None:
            turnarounds.append(turnaround)

    completed = sum(1 for job in jobs if job.status == JobStatus.COMPLETED.value)
    failed = sum(1 for job in jobs if job.status == JobStatus.FAILED.value)
    terminal = sum(1 for job in jobs if job.status in TERMINAL)
    per_tenant = []
    allocations = []
    for bucket in by_tenant.values():
        share = bucket["service"] / bucket["weight"] if bucket["weight"] else 0
        allocations.append(float(share))
        per_tenant.append(
            {
                "tenant_id": bucket["tenant_id"],
                "name": bucket["name"],
                "weight": bucket["weight"],
                "completed": bucket["completed"],
                "failed": bucket["failed"],
                "service": bucket["service"],
                "normalized_service": share,
                "mean_wait": _mean(bucket["waits"]),
            }
        )
    elapsed = elapsed_seconds if elapsed_seconds and elapsed_seconds > 0 else None
    return {
        "job_count": len(jobs),
        "completed": completed,
        "failed": failed,
        "failure_rate": (failed / terminal) if terminal else None,
        "wait_seconds": {"mean": _mean(waits), "p95": percentile(waits, 0.95)},
        "execution_seconds": {"mean": _mean(executions)},
        "turnaround_seconds": {"mean": _mean(turnarounds)},
        "throughput_per_second": (completed / elapsed) if elapsed else None,
        "jain_index": jain_index(allocations),
        "per_tenant": per_tenant,
        "by_priority": {str(priority): _mean(values) for priority, values in sorted(by_priority.items())},
        "elapsed_seconds": elapsed,
    }


def _scoped(tenant_id: UUID | None):
    if tenant_id is None:
        return []
    return [Job.tenant_id == tenant_id]


def summary(session: Session, tenant_id: UUID | None, redis: Redis) -> dict:
    counts = {status.value: 0 for status in JobStatus}
    for status, count in session.execute(
        select(Job.status, func.count()).where(*_scoped(tenant_id)).group_by(Job.status)
    ):
        counts[str(status)] = int(count)
    cutoff = datetime.now(UTC) - timedelta(seconds=60)
    recent = list(
        session.scalars(
            select(Job).where(
                *_scoped(tenant_id),
                Job.finished_at.is_not(None),
                Job.finished_at >= cutoff,
                Job.status.in_(tuple(TERMINAL)),
            )
        )
    )
    settings = get_settings()
    heartbeat_cutoff = datetime.now(UTC) - timedelta(seconds=settings.heartbeat_timeout_seconds)
    worker_count = int(
        session.scalar(
            select(func.count())
            .select_from(Worker)
            .where(
                Worker.state == "HEALTHY",
                Worker.last_heartbeat.is_not(None),
                Worker.last_heartbeat >= heartbeat_cutoff,
            )
        )
        or 0
    )
    try:
        raw_overhead = redis.get("queuepilot:scheduling_overhead_ms")
    except Exception:
        raw_overhead = None
    overhead = float(raw_overhead) if raw_overhead not in (None, "") else None
    body = summarize_jobs(recent, _weights(session), 60.0)
    body["counts"] = counts
    body["queue_depth"] = counts.get(JobStatus.QUEUED.value, 0)
    body["worker_count"] = worker_count
    body["scheduling_overhead_ms"] = overhead
    body["window_seconds"] = 60
    return body


def tenant_statistics(session: Session, tenant_id: UUID | None) -> dict:
    filters = _scoped(tenant_id)
    jobs = list(session.scalars(select(Job).where(*filters)))
    created = [job.created_at for job in jobs if job.created_at is not None]
    finished = [job.finished_at for job in jobs if job.finished_at is not None]
    elapsed = None
    if created and finished:
        elapsed = (max(finished) - min(created)).total_seconds()
    body = summarize_jobs(jobs, _weights(session), elapsed)
    body["counts"] = {}
    return body


def _weights(session: Session) -> dict[UUID, tuple[str, int]]:
    return {tenant.id: (tenant.name, tenant.weight) for tenant in session.scalars(select(Tenant))}
