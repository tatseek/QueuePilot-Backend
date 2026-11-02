from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.scheduler.fifo import choose_fifo
from app.workers.tasks import prepare_task


def test_choose_fifo_picks_oldest_job() -> None:
    older = SimpleNamespace(created_at=datetime(2026, 1, 1, tzinfo=UTC), id=uuid4())
    newer = SimpleNamespace(created_at=datetime(2026, 1, 2, tzinfo=UTC), id=uuid4())
    assert choose_fifo([newer, older]) is older


def test_choose_fifo_breaks_ties_by_id() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    first = SimpleNamespace(created_at=created, id=uuid4())
    second = SimpleNamespace(created_at=created, id=uuid4())
    expected = min((first, second), key=lambda job: job.id)
    assert choose_fifo([second, first]) is expected


def test_choose_fifo_empty() -> None:
    assert choose_fifo([]) is None


def test_prepare_sleep_bounds() -> None:
    payload, cost = prepare_task("sleep", {"duration_seconds": 5})
    assert payload == {"duration_seconds": 5.0}
    assert cost == 5
    with pytest.raises(ValueError):
        prepare_task("sleep", {"duration_seconds": 31})


def test_prepare_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        prepare_task("shell", {})
