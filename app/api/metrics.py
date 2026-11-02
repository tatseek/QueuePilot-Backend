from redis import Redis
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.settings import get_settings
from app.db import get_db
from app.models import User
from app.services.metrics import summary, tenant_statistics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _scope(user: User):
    if user.role == "admin":
        return None
    return user.tenant_id


@router.get("/summary")
def metrics_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return summary(db, _scope(user), _redis())


@router.get("/tenants")
def metrics_tenants(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return tenant_statistics(db, _scope(user))
