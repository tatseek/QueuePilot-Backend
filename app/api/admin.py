from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import BenchmarkRun, ScalingEvent, SchedulerState, Tenant, User
from app.scheduler.policies import POLICIES
from app.services.benchmarks import Workload, build_workload, start_benchmark

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SchedulerOut(BaseModel):
    policy: str


class SchedulerPatch(BaseModel):
    policy: str = Field(pattern="^(fifo|priority|wrr|wdrr)$")


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    weight: int
    max_concurrent_jobs: int


class TenantPatch(BaseModel):
    weight: int = Field(ge=1, le=100)
    max_concurrent_jobs: int = Field(ge=1, le=100)


class BenchmarkCreate(BaseModel):
    algorithm: str = Field(pattern="^(fifo|priority|wrr|wdrr)$")
    seed: int = Field(default=1, ge=0, le=1_000_000)
    preset: str | None = None
    workload: dict | None = None


class BenchmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    algorithm: str
    workload_config: dict
    random_seed: int | None
    metrics: dict | None
    created_at: datetime


class ScalingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    old_worker_count: int
    new_worker_count: int
    reason: str
    timestamp: datetime


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin account required")


def _state(db: Session) -> SchedulerState:
    state = db.get(SchedulerState, 1)
    if state is None:
        state = SchedulerState(id=1, policy="fifo", cursor=0, credits=0, deficits={})
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _reset_fairness(state: SchedulerState) -> None:
    state.cursor = 0
    state.credits = 0
    state.deficits = {}
    state.updated_at = datetime.now(UTC)


@router.get("/scheduler", response_model=SchedulerOut)
def get_scheduler(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SchedulerOut:
    _require_admin(user)
    return SchedulerOut(policy=_state(db).policy)


@router.patch("/scheduler", response_model=SchedulerOut)
def update_scheduler(
    body: SchedulerPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchedulerOut:
    _require_admin(user)
    if body.policy not in POLICIES:
        raise HTTPException(status_code=422, detail="Unknown scheduling policy")
    state = _state(db)
    state.policy = body.policy
    _reset_fairness(state)
    db.commit()
    return SchedulerOut(policy=state.policy)


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TenantOut]:
    _require_admin(user)
    return list(db.scalars(select(Tenant).order_by(Tenant.name)))


@router.patch("/tenants/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: UUID,
    body: TenantPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantOut:
    _require_admin(user)
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.weight = body.weight
    tenant.max_concurrent_jobs = body.max_concurrent_jobs
    _reset_fairness(_state(db))
    db.commit()
    db.refresh(tenant)
    return tenant


@router.post("/benchmarks", status_code=202, response_model=BenchmarkOut)
def create_benchmark(
    body: BenchmarkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BenchmarkRun:
    _require_admin(user)
    if body.algorithm not in POLICIES:
        raise HTTPException(status_code=422, detail="Unknown scheduling policy")
    recent = db.scalars(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(5))
    for existing in recent:
        if (existing.metrics or {}).get("status") == "running":
            raise HTTPException(status_code=409, detail="A benchmark is already running")
    try:
        custom = None if body.preset else Workload.model_validate(body.workload)
        workload = build_workload(body.preset, custom)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return start_benchmark(db, algorithm=body.algorithm, seed=body.seed, workload=workload)


@router.get("/benchmarks", response_model=list[BenchmarkOut])
def list_benchmarks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BenchmarkRun]:
    _require_admin(user)
    return list(db.scalars(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(20)))


@router.get("/benchmarks/{run_id}", response_model=BenchmarkOut)
def get_benchmark(
    run_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BenchmarkRun:
    _require_admin(user)
    run = db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return run


@router.get("/scaling", response_model=list[ScalingOut])
def list_scaling(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ScalingEvent]:
    _require_admin(user)
    return list(db.scalars(select(ScalingEvent).order_by(ScalingEvent.timestamp.desc()).limit(20)))
