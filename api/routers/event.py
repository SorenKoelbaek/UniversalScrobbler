import logging
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from models.sqlmodels import User
from dependencies.auth import get_current_user
from services.redis_sse_service import redis_sse_service
from routers.playback_session import get_device_context
logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events")
async def event_stream(
    request: Request,
    user: User = Depends(get_current_user),
    device: dict = Depends(get_device_context),  # ✅ capture headers here
):
    """Attach an SSE client that listens for Redis PubSub events."""
    return EventSourceResponse(
        redis_sse_service.stream(request, str(user.user_uuid), device)
    )