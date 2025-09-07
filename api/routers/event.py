import logging
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from models.sqlmodels import User
from dependencies.auth import get_current_user
from services.redis_sse_service import redis_sse_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events")
async def event_stream(request: Request, user: User = Depends(get_current_user)):
    """Attach an SSE client that listens for Redis PubSub events."""
    user_uuid = str(user.user_uuid)
    return EventSourceResponse(redis_sse_service.stream(request, user_uuid))
