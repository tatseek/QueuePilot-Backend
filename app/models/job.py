import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JobStatus(enum.StrEnum):
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    RETRY_WAIT = "RETRY_WAIT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


JOB_STATUS_CHECK = (
    "status IN ('QUEUED', 'DISPATCHED', 'RUNNING', 'COMPLETED', "
    "'RETRY_WAIT', 'FAILED', 'CANCELLED')"
)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(JOB_STATUS_CHECK, name="ck_jobs_status"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_tenant_status_created_at", "tenant_id", "status", "created_at"),
        Index("ix_jobs_retry_after", "retry_after"),
        Index(
            "uq_jobs_tenant_idempotency_key",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Larger values are selected first by the priority policy.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    estimated_cost: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'QUEUED'")
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("job_attempts.id", use_alter=True, name="fk_jobs_attempt_id"),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (
        Index("ix_job_attempts_job_id_attempt_number", "job_id", "attempt_number", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("jobs.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workers.id"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
