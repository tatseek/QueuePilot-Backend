import logging
from datetime import UTC, datetime, timedelta

from redis import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import Job, JobAttempt, JobEvent, JobStatus, OutboxEvent, Tenant, Worker

logger = logging.getLogger("queuepilot.scheduler")


def _now() -> datetime:
    return datetime.now(UTC)


def promote_retries(session: Session) -> None:
    now = _now()
    waiting = session.scalars(
        select(Job).where(Job.status == JobStatus.RETRY_WAIT.value, Job.retry_after <= now)
    )
    for job in waiting:
        job.status = JobStatus.QUEUED.value
        job.retry_after = None


def recover_expired_leases(session: Session) -> None:
    now = _now()
    expired = session.scalars(
        select(Job).where(
            Job.status.in_((JobStatus.DISPATCHED.value, JobStatus.RUNNING.value)),
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
        )
    )
    for job in expired:
        old_status = job.status
        if job.attempt_count >= job.max_attempts:
            job.status = JobStatus.FAILED.value
            job.finished_at = now
            job.error_message = "Attempt lease expired"
        else:
            job.status = JobStatus.RETRY_WAIT.value
            job.retry_after = now
            job.lease_expires_at = None
        session.add(
            JobEvent(
                job_id=job.id,
                event_type="lease_expired",
                old_status=old_status,
                new_status=job.status,
            )
        )


def available_slots(session: Session) -> int:
    settings = get_settings()
    cutoff = _now() - timedelta(seconds=settings.heartbeat_timeout_seconds)
    capacities = session.scalars(
        select(Worker.capacity).where(
            Worker.state == "HEALTHY",
            Worker.last_heartbeat.is_not(None),
            Worker.last_heartbeat >= cutoff,
        )
    )
    capacity = sum(capacities)
    inflight = session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.status.in_((JobStatus.DISPATCHED.value, JobStatus.RUNNING.value)))
    )
    return max(0, capacity - int(inflight or 0))


def reserve_next_fifo(session: Session) -> bool:
    now = _now()
    inflight_for_tenant = (
        select(func.count())
        .select_from(Job)
        .where(
            Job.tenant_id == Tenant.id,
            Job.status.in_((JobStatus.DISPATCHED.value, JobStatus.RUNNING.value)),
        )
        .correlate(Tenant)
        .scalar_subquery()
    )
    job = session.scalar(
        select(Job)
        .join(Tenant, Tenant.id == Job.tenant_id)
        .where(
            Job.status == JobStatus.QUEUED.value,
            Job.cancellation_requested.is_(False),
            or_(Job.retry_after.is_(None), Job.retry_after <= now),
            inflight_for_tenant < Tenant.max_concurrent_jobs,
        )
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True, of=Job)
    )
    if job is None:
        return False

    settings = get_settings()
    attempt = JobAttempt(
        job_id=job.id,
        attempt_number=job.attempt_count + 1,
        state=JobStatus.DISPATCHED.value,
    )
    session.add(attempt)
    session.flush()
    job.status = JobStatus.DISPATCHED.value
    job.attempt_id = attempt.id
    job.attempt_count += 1
    job.dispatched_at = now
    job.lease_expires_at = now + timedelta(seconds=settings.lease_seconds)
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="dispatched",
            old_status=JobStatus.QUEUED.value,
            new_status=JobStatus.DISPATCHED.value,
        )
    )
    session.add(
        OutboxEvent(
            event_type="job.dispatch",
            aggregate_id=job.id,
            payload={"job_id": str(job.id), "attempt_id": str(attempt.id)},
        )
    )
    session.commit()
    return True


def publish_outbox(session: Session, redis: Redis) -> None:
    settings = get_settings()
    pending = session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at)
    )
    now = _now()
    for event in pending:
        fields = {"event_id": str(event.id), "event_type": event.event_type}
        for key, value in event.payload.items():
            fields[str(key)] = str(value)
        redis.xadd(settings.dispatch_stream, fields)
        event.published_at = now
        event.attempt_count += 1
    session.commit()


def dispatch_once(session: Session, redis: Redis) -> int:
    promote_retries(session)
    recover_expired_leases(session)
    session.commit()
    publish_outbox(session, redis)
    dispatched = 0
    for _ in range(available_slots(session)):
        if not reserve_next_fifo(session):
            break
        dispatched += 1
    publish_outbox(session, redis)
    return dispatched
