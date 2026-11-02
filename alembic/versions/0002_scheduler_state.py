"""Scheduler policy row."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_scheduler_state"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("policy", sa.String(32), nullable=False, server_default=sa.text("'fifo'")),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "deficits",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "policy IN ('fifo', 'priority', 'wrr', 'wdrr')",
            name="ck_scheduler_state_policy",
        ),
    )
    op.execute("INSERT INTO scheduler_state (id, policy) VALUES (1, 'fifo')")


def downgrade() -> None:
    op.drop_table("scheduler_state")
