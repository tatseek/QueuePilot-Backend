from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleObservation:
    high_streak: int
    low_streak: int
    action: str


def observe_pressure(
    *,
    queued: int,
    healthy: int,
    minimum: int,
    maximum: int,
    high_streak: int,
    low_streak: int,
    samples_required: int = 3,
    high_pressure: float = 10,
    low_pressure: float = 2,
) -> ScaleObservation:
    if healthy < minimum:
        return ScaleObservation(0, 0, "below_minimum")
    pressure = queued / healthy if healthy else 0
    if pressure > high_pressure:
        high_streak += 1
        low_streak = 0
    elif pressure < low_pressure:
        low_streak += 1
        high_streak = 0
    else:
        high_streak = 0
        low_streak = 0
    if high_streak >= samples_required and healthy < maximum:
        return ScaleObservation(high_streak, low_streak, "scale_up")
    if low_streak >= samples_required and healthy > minimum:
        return ScaleObservation(high_streak, low_streak, "scale_down")
    return ScaleObservation(high_streak, low_streak, "hold")
