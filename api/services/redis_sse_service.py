# services/redis_sse_service.py
import asyncio
import json
import logging
from uuid import UUID
from typing import Dict, AsyncIterator

import dependencies.redis as redis_dep  # 👈 import the module, not the variable
from fastapi import Request
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class RedisSSEService:
    """
    Singleton service for handling Server-Sent Events via Redis Pub/Sub.
    - Subscribes once to Redis pattern `us:user:*`
    - Maintains per-user asyncio queues for SSE clients
    - Dispatches Redis events into correct user queues
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._queues: Dict[UUID, asyncio.Queue] = {}

    def add_client(self, user_uuid: UUID) -> asyncio.Queue:
        """Register a new SSE client and return its queue."""
        q = asyncio.Queue(maxsize=50)
        self._queues[user_uuid] = q
        logger.debug(
            f"➕ Added SSE client for {user_uuid}. "
            f"Active clients: {list(self._queues.keys())}"
        )
        return q

    def remove_client(self, user_uuid: UUID) -> None:
        """Remove an SSE client queue when the user disconnects."""
        if user_uuid in self._queues:
            del self._queues[user_uuid]
            logger.info(
                f"➖ Removed SSE client for {user_uuid}. "
                f"Active clients: {list(self._queues.keys())}"
            )

    async def stream(self, request: Request, user_uuid: str) -> AsyncIterator[str]:
        uuid_obj = UUID(user_uuid)
        queue = self.add_client(uuid_obj)
        yield f"{json.dumps({"message": "connected"})}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=5)
                    payload = jsonable_encoder({"message": message})
                    yield f"{json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"  # keepalive
        finally:
            self.remove_client(uuid_obj)

    async def _listen(self):
        """Background Redis pubsub listener that dispatches messages to queues."""

        if redis_dep.redis_client is None:
            return

        try:
            pubsub = redis_dep.redis_client.pubsub()
            await pubsub.psubscribe("us:user:*")
            await pubsub.ping(ignore_subscribe_messages=True)
        except Exception as e:
            logger.exception(f"💥 Failed during pubsub.psubscribe: {e}")
            raise

        try:
            async for message in pubsub.listen():
                if message["type"] not in ("message", "pmessage"):
                    continue

                try:
                    data = json.loads(message["data"])
                    channel = message.get("channel")
                    if isinstance(channel, bytes):
                        channel = channel.decode()

                    if channel and channel.startswith("us:user:"):
                        user_uuid = UUID(channel.split(":")[-1])
                        q = self._queues.get(user_uuid)

                        if q:
                            if q.full():
                                dropped = q.get_nowait()
                                logger.warning(
                                    f"⚠️ Queue full for {user_uuid}, dropped oldest: {dropped}"
                                )
                            await q.put(data)
                            logger.info(f"➡️ Enqueued SSE for {user_uuid}")
                        else:
                            logger.debug(
                                f"👀 No SSE client found for {user_uuid}, skipping"
                            )

                except Exception as e:
                    logger.error(f"❌ Failed to handle pubsub message: {e}")

        except asyncio.CancelledError:
            logger.info("🛑 Redis SSE subscriber cancelled")
            await pubsub.close()
            raise
        except Exception as e:
            logger.error(f"💥 Redis SSE subscriber crashed: {e}")
            raise

    def start(self):
        """Start background Redis listener task (idempotent)."""
        if self._task is None or self._task.done():
            logger.info("▶️ Starting Redis SSE subscriber task…")
            self._task = asyncio.create_task(self._listen())

    def stop(self):
        """Stop background Redis listener task."""
        if self._task:
            logger.info("⏹️ Stopping Redis SSE subscriber task…")
            self._task.cancel()
            self._task = None


# Singleton instance
redis_sse_service = RedisSSEService()
