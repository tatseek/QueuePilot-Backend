# Viva questions

Short answers match this codebase.

**Where does a job live before a worker sees it?** In PostgreSQL, status `QUEUED`. Redis receives one message after the scheduler reserves it.

**Why is tenant id not in the submit body?** The API reads it from the JWT. A client cannot file work into another tenant.

**What stops two schedulers from taking the same job?** The chosen row is locked with `FOR UPDATE SKIP LOCKED`, and the status change commits before publish.

**What is the difference between WRR and WDRR?** WRR spends one credit per job. WDRR adds `weight * quantum` until the job’s estimated cost fits, then subtracts that cost, so a large job does not erase a light tenant’s turn forever.

**What happens if a worker dies mid-job?** Its heartbeat goes stale. When the lease time passes, the scheduler moves the job to `RETRY_WAIT` or `FAILED` if attempts are used up. A redelivered message with an old attempt id is acknowledged and ignored.

**Why not put the Docker socket in the API?** Scaling is a host script, `scripts/autoscaler.py`, so a request to the API cannot start containers.

**What does Jain’s index mean here?** It scores completed cost divided by configured weight. Equal normalized service scores 1. It is reported next to per-tenant wait because a single index hides who waited.

**Are the benchmark charts a proof that WDRR is better?** No. They are one machine, one seed, and a small preset until the repeats in `docs/experiments.md` say otherwise.
