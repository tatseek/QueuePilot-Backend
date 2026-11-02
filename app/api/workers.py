from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import JobAttempt, JobStatus, User, Worker

router = APIRouter(prefix="/api/workers", tags=["workers"])


class WorkerOut(BaseModel):
    id: UUID
    state: str
    capacity: int
    last_heartbeat: datetime | None
    started_at: datetime
    current_job_id: UUID | None
    utilization: float


@router.get("", response_model=list[WorkerOut])
def list_workers(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkerOut]:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin account required")
    current: dict[UUID, UUID] = {}
    attempts = db.scalars(
        select(JobAttempt)
        .where(JobAttempt.state == JobStatus.RUNNING.value, JobAttempt.worker_id.is_not(None))
        .order_by(JobAttempt.started_at)
    )
    for attempt in attempts:
        if attempt.worker_id is not None:
            current[attempt.worker_id] = attempt.job_id
    workers = db.scalars(select(Worker).order_by(Worker.started_at.desc()).limit(50))
    return [
        WorkerOut(
            id=worker.id,
            state=worker.state,
            capacity=worker.capacity,
            last_heartbeat=worker.last_heartbeat,
            started_at=worker.started_at,
            current_job_id=current.get(worker.id),
            utilization=1.0 if worker.id in current else 0.0,
        )
        for worker in workers
    ]
