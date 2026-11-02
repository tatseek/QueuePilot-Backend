import app.models  # noqa: F401
from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.services.seed import DEMO_TENANTS


def test_metadata_contains_roadmap_tables() -> None:
    assert set(Base.metadata.tables) == {
        "tenants",
        "users",
        "jobs",
        "job_attempts",
        "workers",
        "job_events",
        "outbox_events",
        "benchmark_runs",
        "scaling_events",
        "scheduler_state",
    }


def test_job_indexes_match_roadmap() -> None:
    index_names = {index.name for index in Base.metadata.tables["jobs"].indexes}
    assert "ix_jobs_status_created_at" in index_names
    assert "ix_jobs_tenant_status_created_at" in index_names
    assert "ix_jobs_retry_after" in index_names
    assert "uq_jobs_tenant_idempotency_key" in index_names


def test_demo_tenants_use_roadmap_weights() -> None:
    assert [row["weight"] for row in DEMO_TENANTS] == [1, 2, 3]
    assert [row["name"] for row in DEMO_TENANTS] == ["Tenant A", "Tenant B", "Tenant C"]


def test_health_ok(monkeypatch) -> None:
    monkeypatch.setattr("app.api.health.check_database", lambda: None)
    monkeypatch.setattr("app.api.health.check_redis", lambda: None)
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


def test_health_reports_unavailable_dependency(monkeypatch) -> None:
    def fail_database() -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr("app.api.health.check_database", fail_database)
    monkeypatch.setattr("app.api.health.check_redis", lambda: None)
    response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "error",
        "redis": "ok",
    }
