"""Host-side worker autoscaler.

Starts and drains local Python workers. It does not talk to a Docker socket.
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.settings import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Job, JobAttempt, JobStatus, ScalingEvent, Worker  # noqa: E402
from app.services.scaling import observe_pressure  # noqa: E402

RUNTIME = BACKEND_DIR / ".runtime"
STATE_PATH = RUNTIME / "autoscaler.json"


def _python() -> str:
    candidate = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"high_streak": 0, "low_streak": 0, "last_change": 0}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    RUNTIME.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def _healthy_workers(session) -> list[Worker]:
    settings = get_settings()
    cutoff = datetime.now(UTC).timestamp() - settings.heartbeat_timeout_seconds
    workers = list(session.scalars(select(Worker).where(Worker.state == "HEALTHY")))
    fresh = []
    for worker in workers:
        if worker.last_heartbeat is None:
            continue
        if worker.last_heartbeat.timestamp() >= cutoff:
            fresh.append(worker)
    return fresh


def _queued(session) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.QUEUED.value)
        )
        or 0
    )


def _busy_worker_ids(session) -> set:
    rows = session.scalars(
        select(JobAttempt.worker_id).where(
            JobAttempt.state == JobStatus.RUNNING.value,
            JobAttempt.worker_id.is_not(None),
        )
    )
    return {worker_id for worker_id in rows if worker_id is not None}


def spawn_worker() -> subprocess.Popen:
    return subprocess.Popen(
        [_python(), "-m", "app.workers.main"],
        cwd=str(BACKEND_DIR),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )


def _record(session, old: int, new: int, reason: str) -> None:
    session.add(ScalingEvent(old_worker_count=old, new_worker_count=new, reason=reason))
    session.commit()


def tick(state: dict) -> dict:
    settings = get_settings()
    with SessionLocal() as session:
        healthy = _healthy_workers(session)
        observation = observe_pressure(
            queued=_queued(session),
            healthy=len(healthy),
            minimum=settings.autoscaler_min_workers,
            maximum=settings.autoscaler_max_workers,
            high_streak=int(state.get("high_streak", 0)),
            low_streak=int(state.get("low_streak", 0)),
            samples_required=settings.autoscaler_samples,
            high_pressure=settings.autoscaler_high_pressure,
            low_pressure=settings.autoscaler_low_pressure,
        )
        cooled = time.time() - float(state.get("last_change", 0)) >= settings.autoscaler_cooldown_seconds
        old = len(healthy)
        applied = False
        if observation.action == "below_minimum" and cooled:
            gap = settings.autoscaler_min_workers - old
            for _ in range(max(gap, 0)):
                spawn_worker()
            if gap > 0:
                _record(session, old, old + gap, "below minimum worker count")
                state["last_change"] = time.time()
                applied = True
        elif observation.action == "scale_up" and cooled and old < settings.autoscaler_max_workers:
            spawn_worker()
            _record(session, old, old + 1, "queued jobs per worker stayed above the threshold")
            state["last_change"] = time.time()
            applied = True
        elif observation.action == "scale_down" and cooled and old > settings.autoscaler_min_workers:
            busy = _busy_worker_ids(session)
            idle = [worker for worker in healthy if worker.id not in busy]
            idle.sort(key=lambda worker: worker.started_at, reverse=True)
            if idle:
                idle[0].state = "DRAINING"
                session.commit()
                _record(session, old, old - 1, "queue pressure stayed below the threshold")
                state["last_change"] = time.time()
                applied = True
        if applied:
            state["high_streak"] = 0
            state["low_streak"] = 0
        else:
            state["high_streak"] = observation.high_streak
            state["low_streak"] = observation.low_streak
    _save_state(state)
    return state


def main() -> None:
    state = _load_state()
    settings = get_settings()
    while True:
        try:
            state = tick(state)
        except Exception:
            import logging

            logging.getLogger("queuepilot.autoscaler").exception("Autoscaler tick failed")
        time.sleep(settings.autoscaler_interval_seconds)


if __name__ == "__main__":
    main()
