import os
import json
import logging
from typing import Any, Optional
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")

# Connect with decode_responses=True so we get strings back instead of bytes
client: Optional[redis.Redis] = None

if REDIS_URL:
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        # Test connection
        client.ping()
        logger.info("Connected to Redis successfully.")
    except Exception as e:
        logger.warning(f"Redis connection failed, running without cache. Error: {e}")
        client = None


def get_cache(key: str) -> Optional[Any]:
    """Retrieve and deserialize a value from Redis."""
    if not client:
        return None
    try:
        val = client.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.error(f"Cache get error for key {key}: {e}")
    return None


def set_cache(key: str, data: Any, ttl_seconds: int = 300) -> None:
    """Serialize and store a value in Redis with a time-to-live."""
    if not client:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(data))
    except Exception as e:
        logger.error(f"Cache set error for key {key}: {e}")


def invalidate_cache(key_pattern: str) -> None:
    """Delete keys matching a specific pattern (e.g., 'top_books:*')."""
    if not client:
        return
    try:
        keys = client.keys(key_pattern)
        if keys:
            client.delete(*keys)
    except Exception as e:
        logger.error(f"Cache invalidate error for pattern {key_pattern}: {e}")
