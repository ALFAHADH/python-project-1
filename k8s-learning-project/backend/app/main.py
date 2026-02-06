from collections.abc import Generator
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import auth, orders, users
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.utils.logger import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(orders.router, prefix=settings.API_PREFIX)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "k8s-learning-order-platform"}


@app.get("/health/live", tags=["health"])
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def health_ready() -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("Readiness check failed for database", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc

    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except RedisError as exc:
        logger.exception("Readiness check failed for redis", extra={"error": str(exc)})
        raise HTTPException(status_code=503, detail="Redis is unavailable") from exc

    return {"status": "ready", "checks": checks}
