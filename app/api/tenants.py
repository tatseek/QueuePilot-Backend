from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import Tenant, User

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    weight: int
    max_concurrent_jobs: int


class MeOut(BaseModel):
    email: str
    role: str
    tenant: TenantOut | None


@router.get("/me", response_model=MeOut)
def current_tenant(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeOut:
    tenant = None if user.tenant_id is None else db.get(Tenant, user.tenant_id)
    return MeOut(
        email=user.email,
        role=user.role,
        tenant=None
        if tenant is None
        else TenantOut(
            id=tenant.id,
            name=tenant.name,
            weight=tenant.weight,
            max_concurrent_jobs=tenant.max_concurrent_jobs,
        ),
    )
