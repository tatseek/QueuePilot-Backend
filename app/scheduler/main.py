import logging
import time

from redis import Redis

from app.core.settings import get_settings
from app.db import SessionLocal
from app.monitoring.checks import check_database, check_redis
from app.scheduler.dispatch import dispatch_once

logger = logging.getLogger("queuepilot.scheduler")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    check_database()
    check_redis()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Scheduler is selecting queued jobs.")
    while True:
        try:
            with SessionLocal() as session:
                dispatched = dispatch_once(session, redis)
            if dispatched:
                logger.info("Dispatched %s job(s).", dispatched)
        except Exception:
            logger.exception("Scheduler loop failed")
        time.sleep(settings.scheduler_interval_seconds)


if __name__ == "__main__":
    main()
