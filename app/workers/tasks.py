import hashlib
import time
from typing import Any


class TaskCancelled(Exception):
    pass


def prepare_task(job_type: str, params: dict[str, Any]) -> tuple[dict[str, Any], int]:
    if job_type == "sleep":
        duration = params.get("duration_seconds")
        if isinstance(duration, bool) or not isinstance(duration, int | float):
            raise ValueError("duration_seconds must be a number")
        if duration <= 0 or duration > 30:
            raise ValueError("duration_seconds must be between 0 and 30")
        return {"duration_seconds": float(duration)}, max(1, int(duration))

    if job_type == "hash_compute":
        rounds = params.get("rounds")
        if isinstance(rounds, bool) or not isinstance(rounds, int):
            raise ValueError("rounds must be an integer")
        if rounds < 1 or rounds > 100_000:
            raise ValueError("rounds must be between 1 and 100000")
        return {"rounds": rounds}, max(1, rounds // 1000)

    if job_type == "report_generate":
        title = params.get("title")
        rows = params.get("rows")
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ValueError("title must be 1 to 200 characters")
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 1 or rows > 100:
            raise ValueError("rows must be an integer from 1 to 100")
        return {"title": title.strip(), "rows": rows}, rows

    raise ValueError("type must be sleep, hash_compute, or report_generate")


def execute_task(job_type: str, payload: dict[str, Any], should_cancel) -> dict[str, Any]:
    if job_type == "sleep":
        remaining = float(payload["duration_seconds"])
        while remaining > 0:
            if should_cancel():
                raise TaskCancelled()
            step = min(0.2, remaining)
            time.sleep(step)
            remaining -= step
        return {"slept_seconds": payload["duration_seconds"]}

    if job_type == "hash_compute":
        digest = hashlib.sha256(b"queuepilot")
        rounds = int(payload["rounds"])
        for index in range(rounds):
            if index % 2000 == 0 and should_cancel():
                raise TaskCancelled()
            digest.update(str(index).encode())
        return {"rounds": rounds, "sha256": digest.hexdigest()}

    if job_type == "report_generate":
        if should_cancel():
            raise TaskCancelled()
        lines = [f"{payload['title']} row {number}" for number in range(1, int(payload["rows"]) + 1)]
        return {"title": payload["title"], "rows": payload["rows"], "lines": lines}

    raise ValueError(f"Unknown task type {job_type}")
