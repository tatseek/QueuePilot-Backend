import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Tenant

DEMO_TENANTS = (
    {
        "id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "name": "Tenant A",
        "weight": 1,
        "max_concurrent_jobs": 10,
    },
    {
        "id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        "name": "Tenant B",
        "weight": 2,
        "max_concurrent_jobs": 10,
    },
    {
        "id": uuid.UUID("33333333-3333-4333-8333-333333333333"),
        "name": "Tenant C",
        "weight": 3,
        "max_concurrent_jobs": 10,
    },
)


def seed_demo_tenants(session: Session) -> int:
    inserted = 0
    for row in DEMO_TENANTS:
        existing = session.get(Tenant, row["id"])
        same_name = session.scalar(select(Tenant).where(Tenant.name == row["name"]))
        if existing is None and same_name is None:
            session.add(Tenant(**row))
            inserted += 1
    session.commit()
    return inserted


def main() -> None:
    with SessionLocal() as session:
        inserted = seed_demo_tenants(session)
    print(f"Demo tenants ready. Inserted {inserted}.")


if __name__ == "__main__":
    main()
