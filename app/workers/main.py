import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta

from redis import Redis
from redis.exceptions import ResponseError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db import SessionLocal
from app.models import Job, JobAttempt, JobEvent, JobStatus, Worker
from app.monitoring.checks import check_database, check_redis
from app.workers.tasks import TaskCancelled, execute_task

logger = logging.getLogger("queuepilot.worker")


def _now() -> datetime:
    return datetime.now(UTC)


def ensure_group(redis) -> None:
    settings = get_settings()
    try:
        redis.xgroup_create(settings.dispatch_stream, settings.worker_group, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def register_worker(session: Session, worker_id: uuid.UUID) -> None:
    session.add(
        Worker(
            id=worker_id,
            state="HEALTHY",
            capacity=1,
            last_heartbeat=_now(),
        )
    )
    session.commit()


def heartbeat(session: Session, worker_id: uuid.UUID, job_id: uuid.UUID | None) -> None:
    now = _now()
    settings = get_settings()
    session.execute(
        update(Worker)
        .where(Worker.id == worker_id)
        .values(last_heartbeat=now, state="HEALTHY")
    )
    if job_id is not None:
        session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.RUNNING.value)
            .values(lease_expires_at=now + timedelta(seconds=settings.lease_seconds))
        )
        session.execute(
            update(JobAttempt)
            .where(JobAttempt.job_id == job_id, JobAttempt.worker_id == worker_id)
            .values(heartbeat_at=now)
        )
    session.commit()


def _cancelled(session_factory, job_id: uuid.UUID) -> bool:
    with session_factory() as session:
        job = session.get(Job, job_id)
        return job is not None and job.cancellation_requested


def finish_job(session: Session, job: Job, attempt: JobAttempt, *, status: str, result, error: str | None) -> None:
    old_status = job.status
    now = _now()
    job.status = status
    job.finished_at = now
    job.lease_expires_at = None
    job.result = result
    job.error_message = error
    attempt.state = status
    attempt.finished_at = now
    attempt.error = error
    session.add(
        JobEvent(
            job_id=job.id,
            event_type="finished",
            old_status=old_status,
            new_status=status,
            worker_id=attempt.worker_id,
        )
    )
    session.commit()


def handle_delivery(redis, worker_id: uuid.UUID, message_id: str, fields: dict) -> None:
    settings = get_settings()
    job_id = uuid.UUID(fields["job_id"])
    attempt_id = uuid.UUID(fields["attempt_id"])
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        attempt = session.get(JobAttempt, attempt_id)
        if (
            job is None
            or attempt is None
            or job.attempt_id != attempt_id
            or job.status != JobStatus.DISPATCHED.value
        ):
            redis.xack(settings.dispatch_stream, settings.worker_group, message_id)
            return
        now = _now()
        job.status = JobStatus.RUNNING.value
        job.started_at = now
        job.lease_expires_at = now + timedelta(seconds=settings.lease_seconds)
        attempt.state = JobStatus.RUNNING.value
        attempt.worker_id = worker_id
        attempt.started_at = now
        session.commit()
        payload = dict(job.payload)
        job_type = job.type

    try:
        result = execute_task(job_type, payload, lambda: _cancelled(SessionLocal, job_id))
    except TaskCancelled:
        status, result, error = JobStatus.CANCELLED.value, None, None
    except Exception as exc:
        logger.exception("Task failed for job %s", job_id)
        status, result, error = JobStatus.FAILED.value, None, str(exc)
    else:
        status, error = JobStatus.COMPLETED.value, None

    with SessionLocal() as session:
        job = session.get(Job, job_id)
        attempt = session.get(JobAttempt, attempt_id)
        if job is None or attempt is None or job.attempt_id != attempt_id:
            redis.xack(settings.dispatch_stream, settings.worker_group, message_id)
            return
        if status == JobStatus.FAILED.value and job.attempt_count < job.max_attempts:
            job.status = JobStatus.RETRY_WAIT.value
            job.retry_after = _now() + timedelta(seconds=2 ** min(job.attempt_count, 5))
            job.error_message = error
            job.lease_expires_at = None
            attempt.state = JobStatus.FAILED.value
            attempt.finished_at = _now()
            attempt.error = error
            session.commit()
        else:
            finish_job(session, job, attempt, status=status, result=result, error=error)
    redis.xack(settings.dispatch_stream, settings.worker_group, message_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    check_database()
    check_redis()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    ensure_group(redis)
    worker_id = uuid.uuid4()
    with SessionLocal() as session:
        register_worker(session, worker_id)
    consumer = str(worker_id)
    logger.info("Worker %s is waiting for jobs.", worker_id)
    current_job: uuid.UUID | None = None
    while True:
        try:
            with SessionLocal() as session:
                heartbeat(session, worker_id, current_job)
            claimed = redis.xautoclaim(
                settings.dispatch_stream,
                settings.worker_group,
                consumer,
                min_idle_time=10_000,
                start_id="0-0",
                count=1,
            )
            messages = claimed[1] if claimed and len(claimed) > 1 else []
            if not messages:
                batches = redis.xreadgroup(
                    settings.worker_group,
                    consumer,
                    {settings.dispatch_stream: ">"},
                    count=1,
                    block=2000,
                )
                if batches:
                    messages = batches[0][1]
            if not messages:
                current_job = None
                continue
            message_id, fields = messages[0]
            current_job = uuid.UUID(fields["job_id"])
            handle_delivery(redis, worker_id, message_id, fields)
            current_job = None
        except Exception:
            logger.exception("Worker loop failed")
            threading.Event().wait(1)


if __name__ == "__main__":
    main()
