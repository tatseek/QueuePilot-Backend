import logging

from sqlalchemy import text
from redis import Redis

from app.core.settings import get_settings
from app.db import engine

logger = logging.getLogger(__name__)


def check_database() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        raise


def check_redis() -> None:
    client = Redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        client.ping()
    except Exception:
        logger.exception("Redis health check failed")
        raise
    finally:
        client.close()
