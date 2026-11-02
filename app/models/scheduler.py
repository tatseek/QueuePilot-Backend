from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SchedulerState(Base):
    __tablename__ = "scheduler_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'fifo'"))
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deficits: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
