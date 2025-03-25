import json

from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from typing import AsyncIterator
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from services.playback_history_service import PlaybackHistoryService
from models.sqlmodels import User
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()

# Define the event stream that sends updates to the frontend
@router.get("/events")
async def event_stream(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_async_session)):
    """
    SSE endpoint that sends updates to the frontend for a specific user.
    """

    async def event_publisher() -> AsyncIterator[str]:
        while True:
            # Check if the client is still connected, if not, break the loop and stop sending data
            if await request.is_disconnected():
                break

            # Fetch current playback data for the user
            history_service = PlaybackHistoryService(db)
            current_play_msg = await history_service.get_current_play_message(user)

            if current_play_msg:
                yield json.dumps(current_play_msg)

            await asyncio.sleep(10)  # Update every 10 seconds (adjust as needed)

    return EventSourceResponse(event_publisher())
