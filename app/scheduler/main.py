import logging

from app.core.runtime import run_until_stopped
from app.monitoring.checks import check_database, check_redis

logger = logging.getLogger("queuepilot.scheduler")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    check_database()
    check_redis()
    run_until_stopped(
        logger,
        "Scheduler is idle. FIFO selection is added in the scheduling milestone.",
    )


if __name__ == "__main__":
    main()
