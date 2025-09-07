# -*- coding: utf-8 -*-
"""Dependencies for Redis.

This module sets up an async Redis client using redis.asyncio.
Includes:
    - Global client (one per worker process)
    - Dependency injection for FastAPI
    - Proper startup/shutdown handling
"""

from typing import AsyncGenerator
from config import settings
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# Read connection string from Dynaconf
REDIS_URL: str = settings.get("REDIS_URL")

# Global client (initialized in lifespan)
redis_client: redis.Redis | None = None


async def init_redis() -> None:
    """Initialize Redis client (called on app startup)."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info(f"✅ Redis client initialized: {REDIS_URL}")


async def close_redis() -> None:
    """Close Redis client (called on app shutdown)."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """FastAPI dependency that yields the Redis client."""
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized. Did you forget init_redis()?")

    yield redis_client
