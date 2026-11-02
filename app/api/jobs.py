from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Job, JobAttempt, JobEvent, JobStatus, User
from app.workers.tasks import prepare_task

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    type: str
    priority: int = Field(default=0, ge=0, le=10)
    idempotency_key: str | None = Field(default=None, max_length=255)
    params: dict


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_number: int
    state: str
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    type: str
    priority: int
    status: str
    payload: dict
    result: dict | None
    error_message: str | None
    attempt_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempts: list[AttemptOut] = []


def _tenant_id(user: User) -> UUID:
    if user.role != "tenant" or user.tenant_id is None:
        raise HTTPException(status_code=403, detail="A tenant account is required")
    return user.tenant_id


def _visible_jobs(user: User):
    statement = select(Job)
    if user.role != "admin":
        if user.tenant_id is None:
            raise HTTPException(status_code=403, detail="A tenant account is required")
        statement = statement.where(Job.tenant_id == user.tenant_id)
    return statement


def _job_out(job: Job, attempts: list[JobAttempt] | None = None) -> JobOut:
    return JobOut(
        id=job.id,
        tenant_id=job.tenant_id,
        type=job.type,
        priority=job.priority,
        status=job.status,
        payload=job.payload or {},
        result=job.result,
        error_message=job.error_message,
        attempt_count=job.attempt_count,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        attempts=[AttemptOut.model_validate(attempt) for attempt in attempts or []],
    )


@router.post("", status_code=202)
def create_job(
    body: JobCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    tenant_id = _tenant_id(user)
    if body.idempotency_key:
        existing = db.scalar(
            select(Job).where(
                Job.tenant_id == tenant_id,
                Job.idempotency_key == body.idempotency_key,
            )
        )
        if existing is not None:
            response.status_code = 200
            return _job_out(existing)

    try:
        payload, cost = prepare_task(body.type, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = Job(
        tenant_id=tenant_id,
        type=body.type,
        payload=payload,
        priority=body.priority,
        estimated_cost=cost,
        status=JobStatus.QUEUED.value,
        idempotency_key=body.idempotency_key,
    )
    db.add(job)
    db.flush()
    db.add(
        JobEvent(
            job_id=job.id,
            event_type="created",
            old_status=None,
            new_status=JobStatus.QUEUED.value,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if body.idempotency_key:
            existing = db.scalar(
                select(Job).where(
                    Job.tenant_id == tenant_id,
                    Job.idempotency_key == body.idempotency_key,
                )
            )
            if existing is not None:
                response.status_code = 200
                return _job_out(existing)
        raise
    db.refresh(job)
    return _job_out(job)


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    statement = _visible_jobs(user).order_by(Job.created_at.desc()).limit(200)
    if status:
        statement = statement.where(Job.status == status)
    return [_job_out(job) for job in db.scalars(statement)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    job = db.get(Job, job_id)
    if job is None or (user.role != "admin" and job.tenant_id != user.tenant_id):
        raise HTTPException(status_code=404, detail="Job not found")
    attempts = list(
        db.scalars(
            select(JobAttempt).where(JobAttempt.job_id == job.id).order_by(JobAttempt.attempt_number)
        )
    )
    return _job_out(job, attempts)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobOut:
    tenant_id = _tenant_id(user)
    job = db.get(Job, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
        raise HTTPException(status_code=409, detail="Job is already finished")
    old_status = job.status
    if job.status == JobStatus.QUEUED.value:
        job.status = JobStatus.CANCELLED.value
        job.finished_at = datetime.now(UTC)
    else:
        job.cancellation_requested = True
    db.add(
        JobEvent(
            job_id=job.id,
            event_type="cancel_requested",
            old_status=old_status,
            new_status=job.status,
        )
    )
    db.commit()
    db.refresh(job)
    return _job_out(job)
