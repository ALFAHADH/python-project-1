import json
import logging

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.db.models import OrderStatus

logger = logging.getLogger(__name__)
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


def build_order_cache_key(
    user_id: int,
    status_filter: OrderStatus | None,
    skip: int,
    limit: int,
) -> str:
    status_value = status_filter.value if status_filter else "all"
    return f"orders:{user_id}:{status_value}:{skip}:{limit}"


def get_cached_orders(cache_key: str) -> list[dict] | None:
    try:
        cached = redis_client.get(cache_key)
        if not cached:
            return None
        return json.loads(cached)
    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read orders cache", extra={"error": str(exc), "cache_key": cache_key})
        return None


def set_cached_orders(cache_key: str, payload: list[dict], ttl_seconds: int = 30) -> None:
    try:
        redis_client.setex(cache_key, ttl_seconds, json.dumps(payload))
    except RedisError as exc:
        logger.warning("Failed to write orders cache", extra={"error": str(exc), "cache_key": cache_key})


def invalidate_user_order_cache(user_id: int) -> None:
    pattern = f"orders:{user_id}:*"
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except RedisError as exc:
        logger.warning("Failed to invalidate orders cache", extra={"error": str(exc), "pattern": pattern})

