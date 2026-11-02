from collections.abc import Sequence
from typing import Protocol
from datetime import datetime
from uuid import UUID


class FifoJob(Protocol):
    created_at: datetime
    id: UUID


def choose_fifo(jobs: Sequence[FifoJob]) -> FifoJob | None:
    if not jobs:
        return None
    return min(jobs, key=lambda job: (job.created_at, job.id))
