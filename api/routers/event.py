import json

from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from typing import AsyncIterator
from dependencies.auth import get_current_user
from services.websocket_service import WebSocketService
from fastapi.encoders import jsonable_encoder
from models.sqlmodels import User
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/events")
async def event_stream(request: Request, user: User = Depends(get_current_user)):
    """
    SSE endpoint for a specific user's updates.
    """
    queue = WebSocketService.add_sse_client(user.user_uuid)

    async def event_publisher() -> AsyncIterator[str]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=5)
                    payload = jsonable_encoder({"message": message})
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    # Send a ping every 5 seconds to keep the connection alive
                    yield ":\n\n"
        finally:
            WebSocketService.remove_sse_client(user.user_uuid)

    return EventSourceResponse(event_publisher())
