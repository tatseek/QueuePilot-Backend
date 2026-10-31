from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.monitoring.checks import check_database, check_redis

router = APIRouter()


@router.get("/health")
def health() -> JSONResponse:
    database = "ok"
    redis_status = "ok"
    try:
        check_database()
    except Exception:
        database = "error"
    try:
        check_redis()
    except Exception:
        redis_status = "error"

    healthy = database == "ok" and redis_status == "ok"
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "unavailable",
            "database": database,
            "redis": redis_status,
        },
    )
