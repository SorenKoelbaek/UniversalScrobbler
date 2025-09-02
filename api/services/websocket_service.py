from fastapi import WebSocket
from typing import List
from collections import defaultdict
import asyncio
from spotipy import SpotifyException
from uuid import UUID

from models.appmodels import CurrentlyPlaying
from services.spotify_service import SpotifyService
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
import logging
logger = logging.getLogger(__name__)

class WebSocketService:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.sse_clients: dict[UUID, asyncio.Queue] = defaultdict(asyncio.Queue)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        if websocket not in self.active_connections:
            self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific client."""
        await websocket.send_text(message)

    async def send_spotify_token(self, user_uuid, websocket: WebSocket, db: AsyncSession):
        spotify_service = SpotifyService()
        token = await spotify_service.get_token_for_user(user_uuid, db)
        await websocket.send_json({"type": "token", "value": token})

    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        for connection in self.active_connections:
            await connection.send_text(message)

    def add_sse_client(self, user_uuid: UUID) -> asyncio.Queue:
        """Add a new SSE queue for the user."""
        q = asyncio.Queue()
        self.sse_clients[user_uuid] = q
        return q

    def remove_sse_client(self, user_uuid: UUID):
        self.sse_clients.pop(user_uuid, None)

    async def send_to_user(self, user_uuid: UUID, message: CurrentlyPlaying):
        """Push a message to a user's SSE queue."""
        if user_uuid in self.sse_clients:
            await self.sse_clients[user_uuid].put(message)

websocket_service = WebSocketService()