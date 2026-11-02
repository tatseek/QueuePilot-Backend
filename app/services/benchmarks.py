import copy
import threading
import time
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import BenchmarkRun, Job, JobEvent, JobStatus, SchedulerState, Tenant
from app.services.metrics import summarize_jobs
from app.workers.tasks import prepare_task

PRESETS: dict[str, dict] = {
    "fairness": {
        "name": "fairness",
        "arrival": "grouped",
        "jobs": [
            {"tenant": "A", "count": 8, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
            {"tenant": "B", "count": 4, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
            {"tenant": "C", "count": 2, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
        ],
    },
    "priority": {
        "name": "priority",
        "arrival": "grouped",
        "jobs": [
            {"tenant": "A", "count": 6, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 1},
            {"tenant": "A", "count": 4, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 8},
        ],
    },
    "unequal_cost": {
        "name": "unequal_cost",
        "arrival": "grouped",
        "jobs": [
            {"tenant": "A", "count": 4, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
            {"tenant": "B", "count": 4, "type": "hash_compute", "params": {"rounds": 8000}, "priority": 0},
        ],
    },
}

TENANT_NAMES = {"A": "Tenant A", "B": "Tenant B", "C": "Tenant C"}
TERMINAL = {JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value}
MAX_JOBS = 1200


class WorkItem(BaseModel):
    tenant: str = Field(pattern="^[ABC]$")
    count: int = Field(ge=1, le=1200)
    type: str
    params: dict
    priority: int = Field(default=0, ge=0, le=10)


class Workload(BaseModel):
    name: str = "custom"
    arrival: str = "grouped"
    jobs: list[WorkItem]


def build_workload(preset: str | None, custom: Workload | None) -> dict:
    if preset:
        if preset not in PRESETS:
            raise ValueError("preset must be fairness, priority, or unequal_cost")
        workload = copy.deepcopy(PRESETS[preset])
    elif custom is not None:
        workload = custom.model_dump()
    else:
        raise ValueError("Choose a preset or a workload")
    total = sum(item["count"] for item in workload["jobs"])
    if total < 1 or total > MAX_JOBS:
        raise ValueError(f"A run must include 1 to {MAX_JOBS} jobs")
    for item in workload["jobs"]:
        prepare_task(item["type"], item["params"])
        if item["tenant"] not in TENANT_NAMES:
            raise ValueError("tenant must be A, B, or C")
    return workload


def start_benchmark(session: Session, *, algorithm: str, seed: int, workload: dict) -> BenchmarkRun:
    run = BenchmarkRun(
        algorithm=algorithm,
        workload_config=workload,
        random_seed=seed,
        metrics={"status": "running"},
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    threading.Thread(target=_execute, args=(run.id,), name=f"benchmark-{run.id}", daemon=True).start()
    return run


def _set_policy(session: Session, policy: str) -> str:
    state = session.get(SchedulerState, 1)
    if state is None:
        state = SchedulerState(id=1, policy="fifo", cursor=0, credits=0, deficits={})
        session.add(state)
        session.flush()
    previous = state.policy
    state.policy = policy
    state.cursor = 0
    state.credits = 0
    state.deficits = {}
    state.updated_at = datetime.now(UTC)
    session.commit()
    return previous


def _execute(run_id: UUID) -> None:
    previous = None
    try:
        with SessionLocal() as session:
            run = session.get(BenchmarkRun, run_id)
            if run is None:
                return
            previous = _set_policy(session, run.algorithm)
            tenants = {
                tenant.name: tenant
                for tenant in session.scalars(select(Tenant))
            }
            job_ids: list[UUID] = []
            for item in run.workload_config["jobs"]:
                tenant = tenants.get(TENANT_NAMES[item["tenant"]])
                if tenant is None:
                    raise RuntimeError(f"Missing {item['tenant']}")
                payload, cost = prepare_task(item["type"], item["params"])
                for _ in range(item["count"]):
                    job = Job(
                        tenant_id=tenant.id,
                        type=item["type"],
                        payload=payload,
                        priority=item["priority"],
                        estimated_cost=cost,
                        status=JobStatus.QUEUED.value,
                    )
                    session.add(job)
                    session.flush()
                    session.add(
                        JobEvent(
                            job_id=job.id,
                            event_type="created",
                            old_status=None,
                            new_status=JobStatus.QUEUED.value,
                            event_metadata={"benchmark_run_id": str(run_id)},
                        )
                    )
                    job_ids.append(job.id)
            session.commit()
            deadline = time.monotonic() + 900
            jobs: list[Job] = []
            while time.monotonic() < deadline:
                session.expire_all()
                jobs = list(session.scalars(select(Job).where(Job.id.in_(job_ids))))
                if jobs and all(job.status in TERMINAL for job in jobs):
                    break
                session.rollback()
                time.sleep(0.4)
            else:
                session.expire_all()
                jobs = list(session.scalars(select(Job).where(Job.id.in_(job_ids))))
            weights = {tenant.id: (tenant.name, tenant.weight) for tenant in tenants.values()}
            created = [job.created_at for job in jobs if job.created_at is not None]
            finished = [job.finished_at for job in jobs if job.finished_at is not None]
            elapsed = (max(finished) - min(created)).total_seconds() if created and finished else None
            metrics = summarize_jobs(jobs, weights, elapsed)
            unfinished = sum(1 for job in jobs if job.status not in TERMINAL)
            metrics["status"] = "timed_out" if unfinished else "completed"
            metrics["unfinished"] = unfinished
            run = session.get(BenchmarkRun, run_id)
            if run is not None:
                run.metrics = metrics
                session.commit()
    except Exception as exc:
        with SessionLocal() as session:
            run = session.get(BenchmarkRun, run_id)
            if run is not None:
                run.metrics = {"status": "failed", "error": str(exc)}
                session.commit()
    finally:
        if previous is not None:
            with SessionLocal() as session:
                _set_policy(session, previous)
