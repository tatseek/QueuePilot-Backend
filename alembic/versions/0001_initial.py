"""Initial QueuePilot schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_concurrent_jobs", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_users_tenant_id_tenants"),
    )
    op.create_table(
        "workers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'QUEUED'")),
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "cancellation_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'DISPATCHED', 'RUNNING', 'COMPLETED', "
            "'RETRY_WAIT', 'FAILED', 'CANCELLED')",
            name="ck_jobs_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_jobs_tenant_id_tenants"),
    )
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"])
    op.create_index(
        "ix_jobs_tenant_status_created_at",
        "jobs",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index("ix_jobs_retry_after", "jobs", ["retry_after"])
    op.create_index(
        "uq_jobs_tenant_idempotency_key",
        "jobs",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_table(
        "job_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_attempts_job_id_jobs"),
        sa.ForeignKeyConstraint(
            ["worker_id"], ["workers.id"], name="fk_job_attempts_worker_id_workers"
        ),
    )
    op.create_index(
        "ix_job_attempts_job_id_attempt_number",
        "job_attempts",
        ["job_id", "attempt_number"],
        unique=True,
    )
    op.create_foreign_key(
        "fk_jobs_attempt_id",
        "jobs",
        "job_attempts",
        ["attempt_id"],
        ["id"],
    )
    op.create_table(
        "job_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_events_job_id_jobs"),
        sa.ForeignKeyConstraint(
            ["worker_id"], ["workers.id"], name="fk_job_events_worker_id_workers"
        ),
    )
    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "benchmark_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column(
            "workload_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "scaling_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("old_worker_count", sa.Integer(), nullable=False),
        sa.Column("new_worker_count", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("scaling_events")
    op.drop_table("benchmark_runs")
    op.drop_table("outbox_events")
    op.drop_table("job_events")
    op.drop_constraint("fk_jobs_attempt_id", "jobs", type_="foreignkey")
    op.drop_table("job_attempts")
    op.drop_index("uq_jobs_tenant_idempotency_key", table_name="jobs")
    op.drop_index("ix_jobs_retry_after", table_name="jobs")
    op.drop_index("ix_jobs_tenant_status_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("workers")
    op.drop_table("users")
    op.drop_table("tenants")
