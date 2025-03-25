from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from uuid import UUID
from typing import Dict, List
from dependencies.auth import get_current_user_ws
from services.playback_history_service import PlaybackHistoryService
from services.connection_manager import manager
from config import settings
from dependencies.database import get_async_session
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["websocket"],
    include_in_schema=False
)

active_connections: Dict[UUID, List[WebSocket]] = {}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    logger.info("⏳ Authenticating WebSocket user...")
    user = await get_current_user_ws(websocket)
    logger.info(f"✅ WebSocket user authenticated: {user}")
    manager.connect(user.user_uuid, websocket)

    if not user:
        return

    logger.info(f"🔌 {user.username} connected.")

    # Get DB session
    async for db in get_async_session():
        history_service = PlaybackHistoryService(db)
        current_play_msg = await history_service.get_current_play_message(user)
        await websocket.send_json(current_play_msg)
        break  # We only want one session instance for now

    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(user.user_uuid, websocket)
        logger.info(f"❌ {user.username} disconnected.")
