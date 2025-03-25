from typing import Dict, List
from uuid import UUID
from fastapi import WebSocket
import asyncio
from config import settings
import logging


logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

    def connect(self, user_id: UUID, websocket: WebSocket):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user_async(self, user_id: UUID, message: str):
        to_remove = []

        for ws in self.active_connections.get(user_id, []):
            try:
                logger.info(f"Sending message to {ws}: {message}")
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {ws}: {e}")
                to_remove.append(ws)

        for ws in to_remove:
            self.disconnect(user_id, ws)


    def send_to_user(self, user_id: UUID, message: str):
        # Run safely from a sync context
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.send_to_user_async(user_id, message), loop
            )
        else:
            # This happens in isolated tests or scripts
            asyncio.run(self.send_to_user_async(user_id, message))

    def has_connections(self, user_id: UUID):
        return user_id in self.active_connections

# Singleton instance
manager = ConnectionManager()
