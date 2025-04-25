
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from services.shared import websocket_service
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError
from services.playback_history_service import PlaybackHistoryService
from typing import List
from config import settings
import logging
logger = logging.getLogger(__name__)



router = APIRouter()
# OAuth2 Bearer Token for authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, db: AsyncSession = Depends(get_async_session)):
    """WebSocket endpoint to accept connections with authentication."""
    playback_history_service = PlaybackHistoryService(db, websocket_service)
    try:
        # Manually authenticate the user using the token
        user = await get_current_user(token=token, db=db)

        # Establish the WebSocket connection
        await websocket_service.connect(websocket)

        # Send a welcome message to the user
        await websocket_service.send_spotify_token(user.user_uuid, websocket, db)

        while True:
            data = await websocket.receive_text()
            logger.debug(f"🔍 Backend received WS message: {data!r}")
            from models.appmodels import websocketMessage
            try:
                message = websocketMessage.model_validate_json(data)
                if message.type == "playback_update":
                    await playback_history_service.add_listen(user, message.payload)
            except ValidationError as e:
                logger.error(f"WS payload failed schema validation: {e}")

            # Example: if the message contains the keyword "broadcast", trigger SSE broadcast
            if "broadcast" in data:
                # Triggering event to SSE clients based on the WebSocket message content
                await websocket_service.broadcast_to_sse_clients(f"Broadcast message: {data}")

    except HTTPException as e:
        logger.error(f"Error during WebSocket authentication: {e.detail}")
        await websocket.close()
        raise e  # Raising the exception will terminate the WebSocket connection
    except WebSocketDisconnect:
        logger.info("A client disconnected.")
        websocket_service.disconnect(websocket)