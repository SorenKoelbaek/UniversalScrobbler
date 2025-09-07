from fastapi import APIRouter, Depends
from dependencies.redis import get_redis
import redis.asyncio as redis

router = APIRouter(
    prefix="/healthcheck",
    tags=["healthcheck"]
)

@router.get("/redis-health")
async def redis_test(r: redis.Redis = Depends(get_redis)):
    pong = await r.ping()
    return {"pong": pong}

@router.get("/health")
async def health():
    return {"health": "Yes, I am healthy!"}
