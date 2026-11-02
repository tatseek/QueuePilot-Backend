from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

POLICIES = ("fifo", "priority", "wrr", "wdrr")
BASE_QUANTUM = 1


class ScheduledJob(Protocol):
    created_at: datetime
    id: UUID
    tenant_id: str
    priority: int
    cost: int


class ScheduledTenant(Protocol):
    id: str
    weight: int


@dataclass
class FairnessState:
    cursor: int = 0
    credits: int = 0
    deficits: dict[str, int] = field(default_factory=dict)


def choose_fifo(jobs: list[ScheduledJob]) -> ScheduledJob | None:
    if not jobs:
        return None
    return min(jobs, key=lambda job: (job.created_at, job.id))


def choose_priority(jobs: list[ScheduledJob]) -> ScheduledJob | None:
    if not jobs:
        return None
    return min(jobs, key=lambda job: (-job.priority, job.created_at, job.id))


def choose_wrr(
    tenants: list[ScheduledTenant],
    jobs_by_tenant: dict[str, list[ScheduledJob]],
    state: FairnessState,
) -> ScheduledJob | None:
    count = len(tenants)
    if count == 0:
        return None
    for _ in range(count):
        index = state.cursor % count
        tenant = tenants[index]
        queue = jobs_by_tenant.get(tenant.id, [])
        if not queue:
            state.cursor = (index + 1) % count
            state.credits = 0
            continue
        if state.credits <= 0:
            state.credits = max(1, tenant.weight)
        state.credits -= 1
        if state.credits <= 0:
            state.cursor = (index + 1) % count
        return queue[0]
    return None


def choose_wdrr(
    tenants: list[ScheduledTenant],
    jobs_by_tenant: dict[str, list[ScheduledJob]],
    state: FairnessState,
) -> ScheduledJob | None:
    count = len(tenants)
    if count == 0:
        return None
    start = state.cursor % count
    for step in range(count):
        index = (start + step) % count
        tenant = tenants[index]
        queue = jobs_by_tenant.get(tenant.id, [])
        if not queue:
            state.deficits[tenant.id] = 0
            continue
        job = queue[0]
        allowance = BASE_QUANTUM * max(1, tenant.weight)
        deficit = state.deficits.get(tenant.id, 0)
        if deficit < job.cost:
            deficit += allowance
        deficit = min(deficit, max(job.cost, allowance * 4))
        if job.cost <= deficit:
            state.deficits[tenant.id] = deficit - job.cost
            following = queue[1] if len(queue) > 1 else None
            if following is not None and following.cost <= state.deficits[tenant.id]:
                state.cursor = index
            else:
                state.cursor = (index + 1) % count
            return job
        state.deficits[tenant.id] = deficit
    state.cursor = (start + 1) % count
    return None
