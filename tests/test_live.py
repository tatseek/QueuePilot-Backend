import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.main import app
from app.monitoring.checks import check_database, check_redis


def _client() -> TestClient:
    try:
        check_database()
        check_redis()
    except Exception as exc:
        pytest.skip(f"local database is not running: {exc}")
    return TestClient(app)


def _login(client: TestClient, email: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": "queuepilot"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] in {"admin", "tenant"}
    return body["access_token"]


def test_tenant_cannot_list_workers() -> None:
    client = _client()
    token = _login(client, "a@queuepilot.local")
    response = client.get("/api/workers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_admin_metrics_and_scheduler_settings() -> None:
    client = _client()
    token = _login(client, "admin@queuepilot.local")
    headers = {"Authorization": f"Bearer {token}"}
    summary = client.get("/api/metrics/summary", headers=headers)
    tenants = client.get("/api/admin/tenants", headers=headers)
    workers = client.get("/api/workers", headers=headers)
    assert summary.status_code == 200
    assert "queue_depth" in summary.json()
    assert tenants.status_code == 200
    assert len(tenants.json()) >= 3
    assert workers.status_code == 200


def test_tenant_cannot_read_another_tenants_job() -> None:
    client = _client()
    owner = _login(client, "a@queuepilot.local")
    created = client.post(
        "/api/jobs",
        headers={"Authorization": f"Bearer {owner}"},
        json={"type": "hash_compute", "priority": 0, "params": {"rounds": 1}},
    )
    assert created.status_code == 202
    other = _login(client, "b@queuepilot.local")
    hidden = client.get(
        f"/api/jobs/{created.json()['id']}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert hidden.status_code == 404
