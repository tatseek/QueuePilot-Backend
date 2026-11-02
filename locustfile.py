from locust import HttpUser, between, task


class TenantSubmitter(HttpUser):
    wait_time = between(0.2, 1)

    def on_start(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"email": "a@queuepilot.local", "password": "queuepilot"},
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]

    @task
    def submit_hash(self) -> None:
        self.client.post(
            "/api/jobs",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"type": "hash_compute", "priority": 0, "params": {"rounds": 1000}},
        )
