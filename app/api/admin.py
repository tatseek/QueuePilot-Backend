from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import SchedulerState, User
from app.scheduler.policies import POLICIES

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SchedulerOut(BaseModel):
    policy: str


class SchedulerPatch(BaseModel):
    policy: str = Field(pattern="^(fifo|priority|wrr|wdrr)$")


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
    state.cursor = 0
    state.credits = 0
    state.deficits = {}
    state.updated_at = datetime.now(UTC)
    db.commit()
    return SchedulerOut(policy=state.policy)
