import logging

from app.core.runtime import run_until_stopped
from app.monitoring.checks import check_database, check_redis

logger = logging.getLogger("queuepilot.worker")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    check_database()
    check_redis()
    run_until_stopped(
        logger,
        "Worker is idle. Task execution is added in the workers milestone.",
    )


if __name__ == "__main__":
    main()
