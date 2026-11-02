import pytest

from app.services.benchmarks import build_workload
from app.services.metrics import jain_index, percentile
from app.services.scaling import observe_pressure
from app.workers.retry import retry_delay_seconds


def test_percentile_interpolates_the_upper_tail() -> None:
    assert percentile([1, 2, 3, 4], 0.95) == pytest.approx(3.85)
    assert percentile([], 0.95) is None


def test_jain_index_is_one_for_equal_shares() -> None:
    assert jain_index([1, 1, 1]) == pytest.approx(1)
    assert jain_index([1, 0]) == pytest.approx(0.5)
    assert jain_index([]) is None


def test_retry_delay_is_bounded() -> None:
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(3) == 8
    assert retry_delay_seconds(9) == 32


def test_scale_up_waits_for_three_high_samples() -> None:
    streak = observe_pressure(
        queued=30, healthy=2, minimum=1, maximum=5, high_streak=0, low_streak=0
    )
    assert streak.action == "hold"
    ready = observe_pressure(
        queued=30, healthy=2, minimum=1, maximum=5, high_streak=2, low_streak=0
    )
    assert ready.action == "scale_up"
    assert ready.high_streak == 3


def test_scale_down_stops_at_the_minimum() -> None:
    decision = observe_pressure(
        queued=0, healthy=1, minimum=1, maximum=5, high_streak=0, low_streak=3
    )
    assert decision.action == "hold"


def test_missing_workers_scale_immediately() -> None:
    decision = observe_pressure(
        queued=0, healthy=0, minimum=1, maximum=5, high_streak=0, low_streak=0
    )
    assert decision.action == "below_minimum"


def test_preset_workload_stays_within_the_cap() -> None:
    workload = build_workload("fairness", None)
    assert sum(item["count"] for item in workload["jobs"]) <= 100


def test_unknown_preset_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_workload("not-a-preset", None)
