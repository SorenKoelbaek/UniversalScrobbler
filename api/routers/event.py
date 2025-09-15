from datetime import datetime, UTC
import json
import logging
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from models.sqlmodels import User
from dependencies.auth import get_current_user
from services.redis_sse_service import redis_sse_service
from routers.playback_session import get_device_context
import dependencies.redis as redis_dep

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events")
async def event_stream(
    request: Request,
    user: User = Depends(get_current_user),
    device: dict = Depends(get_device_context),
):
    """Attach an SSE client that listens for Redis PubSub events."""
    return EventSourceResponse(
        redis_sse_service.stream(request, str(user.user_uuid), device)
    )


@router.post("/ping")
async def ping(user: User = Depends(get_current_user), payload: dict = None):
    device_uuid = payload.get("device_uuid")
    if not device_uuid:
        return {"status": "error", "reason": "missing device_uuid"}

    redis_key = f"us:active_devices:{user.user_uuid}"
    raw = await redis_dep.redis_client.hget(redis_key, device_uuid)
    if not raw:
        return {"status": "error", "reason": "device not found"}

    meta = json.loads(raw)
    meta["last_seen"] = datetime.now(UTC).isoformat()
    await redis_dep.redis_client.hset(redis_key, device_uuid, json.dumps(meta))

    return {"status": "ok"}
