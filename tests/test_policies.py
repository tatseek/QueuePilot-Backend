from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.scheduler.policies import FairnessState, choose_priority, choose_wrr, choose_wdrr


def _job(tenant: str, stamp: datetime, *, priority: int = 0, cost: int = 1):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant,
        created_at=stamp,
        priority=priority,
        cost=cost,
    )


def _tenant(tenant_id: str, weight: int):
    return SimpleNamespace(id=tenant_id, weight=weight)


def test_priority_prefers_higher_priority_then_older_job() -> None:
    older_low = _job("a", datetime(2026, 1, 1, tzinfo=UTC), priority=1)
    newer_high = _job("b", datetime(2026, 1, 2, tzinfo=UTC), priority=5)
    same_priority_older = _job("c", datetime(2026, 1, 1, tzinfo=UTC), priority=5)
    chosen = choose_priority([older_low, newer_high, same_priority_older])
    assert chosen is same_priority_older


def test_wrr_serves_tenants_in_weight_proportion() -> None:
    tenants = [_tenant("a", 1), _tenant("b", 3)]
    queues = {
        "a": [_job("a", datetime(2026, 1, 1, tzinfo=UTC)) for _ in range(4)],
        "b": [_job("b", datetime(2026, 1, 1, tzinfo=UTC)) for _ in range(4)],
    }
    state = FairnessState()
    served = []
    for _ in range(4):
        chosen = choose_wrr(tenants, queues, state)
        assert chosen is not None
        served.append(chosen.tenant_id)
        queues[chosen.tenant_id].pop(0)
    assert served == ["a", "b", "b", "b"]


def test_wdrr_lets_a_small_tenant_run_between_large_jobs() -> None:
    tenants = [_tenant("a", 1), _tenant("b", 1)]
    queues = {
        "a": [_job("a", datetime(2026, 1, 1, tzinfo=UTC), cost=3)],
        "b": [_job("b", datetime(2026, 1, 1, tzinfo=UTC), cost=1) for _ in range(3)],
    }
    state = FairnessState()
    served = []
    for _ in range(4):
        chosen = choose_wdrr(tenants, queues, state)
        if chosen is None:
            break
        served.append(chosen.tenant_id)
        queues[chosen.tenant_id].pop(0)
    assert served[0] == "b"
    assert "a" in served


def test_wdrr_resets_deficit_for_an_idle_tenant() -> None:
    tenants = [_tenant("a", 2), _tenant("b", 1)]
    state = FairnessState(deficits={"a": 5, "b": 4})
    queues = {"b": [_job("b", datetime(2026, 1, 1, tzinfo=UTC), cost=1)]}
    chosen = choose_wdrr(tenants, queues, state)
    assert chosen is not None
    assert state.deficits["a"] == 0
    assert chosen.tenant_id == "b"
