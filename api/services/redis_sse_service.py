# services/redis_sse_service.py
import asyncio
import json
import logging
from uuid import UUID
from typing import Dict

from sqlmodel import select
import dependencies.redis as redis_dep
from dependencies.database import get_async_session
from services.playback_service import PlaybackService
from fastapi.encoders import jsonable_encoder
from fastapi import Request
from models.sqlmodels import PlaybackSession

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
        self._heartbeat_task: asyncio.Task | None = None

    def add_client(self, user_uuid: UUID) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=50)
        self._queues[user_uuid] = q
        logger.debug(f"➕ Added SSE client for {user_uuid}. Active: {list(self._queues.keys())}")
        return q

    def remove_client(self, user_uuid: UUID) -> None:
        if user_uuid in self._queues:
            del self._queues[user_uuid]
            logger.info(f"➖ Removed SSE client for {user_uuid}. Active: {list(self._queues.keys())}")

    async def stream(self, request: Request, user_uuid: str):
        uuid_obj = UUID(user_uuid)
        queue = self.add_client(uuid_obj)

        # 🔹 Send initial snapshot
        try:
            db_gen = get_async_session()
            db = await anext(db_gen)
            try:
                service = PlaybackService(db, redis_dep.redis_client)
                state = await service.get_state(uuid_obj)

                initial_payload = {
                    "rev": 1,
                    "type": "timeline",
                    "ts": int(asyncio.get_running_loop().time() * 1000),
                }

                if state.now_playing:
                    initial_payload["now_playing"] = {
                        "track_uuid": str(state.now_playing.track.track_uuid),
                        "title": state.now_playing.track.name,
                        "artist": (
                            state.now_playing.track.artists[0].name
                            if state.now_playing.track.artists else "—"
                        ),
                        "album": (
                            state.now_playing.track.albums[0].title
                            if state.now_playing.track.albums else "—"
                        ),
                        "duration_ms": state.now_playing.duration_ms,
                        "file_url": state.now_playing.file_url,
                        "position_ms": 0,
                    }
                    initial_payload["play_state"] = "paused"

                yield f"{json.dumps(jsonable_encoder(initial_payload))}\n\n"
                logger.debug(f"📡 Sent initial snapshot to {user_uuid}: {initial_payload}")
            finally:
                await db_gen.aclose()
        except Exception as e:
            logger.error(f"❌ Failed to send initial snapshot for {user_uuid}: {e}")

        # 🔹 Process queue
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=5)
                    yield f"{json.dumps(jsonable_encoder(message))}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"  # SSE keepalive
        finally:
            self.remove_client(uuid_obj)

    async def _listen(self):
        if redis_dep.redis_client is None:
            return

        try:
            pubsub = redis_dep.redis_client.pubsub()
            await pubsub.psubscribe("us:user:*")
            await pubsub.ping()
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
                                logger.warning(f"⚠️ Queue full for {user_uuid}, dropped: {dropped}")
                            await q.put(data)
                            logger.info(f"➡️ Enqueued SSE for {user_uuid}: {data}")
                        else:
                            logger.debug(f"👀 No SSE client for {user_uuid}, skipping")

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
        if self._task is None or self._task.done():
            logger.info("▶️ Starting Redis SSE subscriber task…")
            self._task = asyncio.create_task(self._listen())
        if self._heartbeat_task is None or self._heartbeat_task.done():
            logger.info("💓 Starting heartbeat loop…")
            self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    def stop(self):
        if self._task:
            logger.info("⏹️ Stopping Redis SSE subscriber task…")
            self._task.cancel()
            self._task = None
        if self._heartbeat_task:
            logger.info("⏹️ Stopping heartbeat loop…")
            self._heartbeat_task.cancel()
            self._heartbeat_task = None


async def heartbeat_loop():
    """Periodically publish playback heartbeats for all active sessions."""


    while True:
        try:
            db_gen = get_async_session()
            db = await anext(db_gen)
            try:
                result = await db.execute(select(PlaybackSession.user_uuid))
                user_ids = [row[0] for row in result.all()]
                for user_uuid in user_ids:
                    service = PlaybackService(db, redis_dep.redis_client)
                    await service._publish_heartbeat(user_uuid)
            finally:
                await db_gen.aclose()
        except Exception as e:
            logger.error(f"💥 Heartbeat loop failed: {e}")

        await asyncio.sleep(5)  # every 5s


# Singleton instance
redis_sse_service = RedisSSEService()
