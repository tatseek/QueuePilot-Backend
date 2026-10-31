# Experiments

No benchmark runs have been recorded. The comparisons below are the ones the project will run after scheduling and workers can complete jobs.

| Experiment | Workload | Comparison |
|---|---|---|
| Fairness | A=1000, B=50, C=10 | FIFO vs WDRR |
| Priority | Mixed high and low priority | FIFO vs priority |
| Unequal job costs | Short and long tasks | WRR vs WDRR |
| Scaling | Bursty arrivals | Fixed vs adaptive workers |
| Failure | Kill a worker mid-job | Recovery latency and correctness |
| Load | Increasing concurrent submissions | Throughput and p95 wait |

Each run keeps the worker count, workload, random seed, and algorithm configuration fixed, then repeats so the report can show variability. Results are measured from the database timestamps. They are not filled in ahead of the runs.

Fairness uses Jain's index on service divided by tenant weight, only over intervals where the compared tenants are backlogged. Per-tenant waiting time is reported beside that score.
