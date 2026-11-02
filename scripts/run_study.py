"""Run the roadmap fairness study and print measured waits.

Submits A=1000, B=50, C=10 equal-cost hash jobs under fifo, then the same
workload under wdrr. Requires the API, scheduler, and workers to be running.
"""

import json
import time
import urllib.request

API = "http://127.0.0.1:8000"
WORKLOAD = {
    "name": "fairness-study",
    "arrival": "grouped",
    "jobs": [
        {"tenant": "A", "count": 1000, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
        {"tenant": "B", "count": 50, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
        {"tenant": "C", "count": 10, "type": "hash_compute", "params": {"rounds": 1000}, "priority": 0},
    ],
}


def _request(path: str, token: str | None, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(API + path, data=data, headers=headers, method="POST" if body else "GET")
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def _wait(token: str, run_id: str) -> dict:
    while True:
        current = _request(f"/api/admin/benchmarks/{run_id}", token)
        status = (current.get("metrics") or {}).get("status")
        print(f"{current['algorithm']} {status}", flush=True)
        if status and status != "running":
            return current
        time.sleep(5)


def main() -> None:
    token = _request(
        "/api/auth/login",
        None,
        {"email": "admin@queuepilot.local", "password": "queuepilot"},
    )["access_token"]
    for algorithm in ("fifo", "wdrr"):
        created = _request(
            "/api/admin/benchmarks",
            token,
            {"algorithm": algorithm, "seed": 1, "workload": WORKLOAD},
        )
        finished = _wait(token, created["id"])
        metrics = finished["metrics"]
        print(
            json.dumps(
                {
                    "algorithm": algorithm,
                    "status": metrics.get("status"),
                    "mean": (metrics.get("wait_seconds") or {}).get("mean"),
                    "p95": (metrics.get("wait_seconds") or {}).get("p95"),
                    "jain": metrics.get("jain_index"),
                    "throughput": metrics.get("throughput_per_second"),
                    "unfinished": metrics.get("unfinished"),
                    "tenants": {
                        row["name"]: row.get("mean_wait") for row in metrics.get("per_tenant") or []
                    },
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
