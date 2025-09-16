# services/redis_sse_service.py
import asyncio
import json
import logging
from uuid import UUID
from typing import Dict
from datetime import datetime, UTC, timedelta
from sqlmodel import select
import dependencies.redis as redis_dep
from dependencies.database import get_async_session
from services.playback_service import PlaybackService
from fastapi.encoders import jsonable_encoder
from fastapi import Request
from models.sqlmodels import PlaybackSession, Device
import copy

logger = logging.getLogger(__name__)

STALE_DEVICE_THRESHOLD = timedelta(seconds=60)  # tune as needed

class RedisSSEService:
    """
    Singleton service for handling Server-Sent Events via Redis Pub/Sub.
    - Subscribes once to Redis pattern `us:user:*`
    - Maintains per-user asyncio queues for SSE clients
    - Dispatches Redis events into correct user queues
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._queues: Dict[tuple[UUID, UUID], asyncio.Queue] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._active_devices: Dict[UUID, dict] = {}

    async def _cleanup_stale_devices(self):
        """Mark devices as disconnected if they haven't been seen recently."""
        try:
            keys = await redis_dep.redis_client.keys("us:active_devices:*")
            now = datetime.now(UTC)

            for redis_key in keys:
                raw_devices = await redis_dep.redis_client.hgetall(redis_key)

                for dev_uuid, payload in raw_devices.items():
                    try:
                        meta = json.loads(payload)
                    except Exception:
                        continue

                    # Parse last_seen
                    try:
                        last_seen = datetime.fromisoformat(meta.get("last_seen"))
                    except Exception:
                        last_seen = now

                    if meta.get("connected") and last_seen < (now - STALE_DEVICE_THRESHOLD):
                        meta["connected"] = False
                        meta["last_seen"] = now.isoformat()
                        await redis_dep.redis_client.hset(redis_key, dev_uuid, json.dumps(meta))
                        logger.info(f"🧹 Cleaned up stale device {dev_uuid} in {redis_key}")
        except Exception as e:
            logger.error(f"💥 Failed during stale device cleanup: {e}")

    async def add_client(self, user_uuid: UUID, device_uuid: UUID, device_name: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=50)
        self._queues[(user_uuid, device_uuid)] = q

        device_meta = {
            "name": device_name,
            "connected": True,
            "last_seen": datetime.now(UTC).isoformat(),
        }

        if user_uuid not in self._active_devices:
            self._active_devices[user_uuid] = {}
        self._active_devices[user_uuid][str(device_uuid)] = device_meta

        redis_key = f"us:active_devices:{user_uuid}"
        await redis_dep.redis_client.hset(
            redis_key,
            str(device_uuid),
            json.dumps(device_meta),
        )


        raw_devices = await redis_dep.redis_client.hgetall(redis_key)
        connected = [
            k for k, v in raw_devices.items()
            if json.loads(v).get("connected")
        ]
        if len(connected) == 1:
            db_gen = get_async_session()
            db = await anext(db_gen)
            try:
                service = PlaybackService(db, redis_dep.redis_client)
                await service.start_new_session(user_uuid)
            finally:
                await db_gen.aclose()


        await redis_dep.redis_client.publish(
            f"us:user:{user_uuid}",
            json.dumps({"type": "devices_changed"})
        )

        logger.info(f"➕ Added device {device_name} ({device_uuid}) for {user_uuid}")
        return q

    async def remove_client(self, user_uuid: UUID, device_uuid: UUID) -> None:
        # Remove local queue
        self._queues.pop((user_uuid, device_uuid), None)

        if user_uuid in self._active_devices and str(device_uuid) in self._active_devices[user_uuid]:
            self._active_devices[user_uuid][str(device_uuid)]["connected"] = False
            self._active_devices[user_uuid][str(device_uuid)]["last_seen"] = datetime.now(UTC).isoformat()
            device_meta = self._active_devices[user_uuid][str(device_uuid)]
        else:
            device_meta = {
                "name": "Unknown",
                "connected": False,
                "last_seen": datetime.now(UTC).isoformat(),
            }

        redis_key = f"us:active_devices:{user_uuid}"
        await redis_dep.redis_client.hset(
            redis_key,
            str(device_uuid),
            json.dumps(device_meta),
        )


        raw_devices = await redis_dep.redis_client.hgetall(redis_key)
        connected = [
            k for k, v in raw_devices.items()
            if json.loads(v).get("connected")
        ]
        if not connected:
            db_gen = get_async_session()
            db = await anext(db_gen)
            try:
                service = PlaybackService(db, redis_dep.redis_client)
                await service.stop_session(user_uuid)
            finally:
                await db_gen.aclose()

        # Broadcast device list change
        await redis_dep.redis_client.publish(
            f"us:user:{user_uuid}",
            json.dumps({"type": "devices_changed"})
        )

        logger.info(f"➖ Removed device {device_uuid} for {user_uuid}")

    async def stream(self, request: Request, user_uuid: str, device: dict | None = None):
        uuid_obj = UUID(user_uuid)
        logger.info(f"received device {device} in redis service")

        this_device_id = device.get("device_id") if device else None
        this_device_name = device.get("device_name") if device else None

        try:
            db_gen = get_async_session()
            db = await anext(db_gen)
            try:
                service = PlaybackService(db, redis_dep.redis_client)
                session = await service._get_or_create_session(
                    uuid_obj,
                    device_id=this_device_id,
                    device_name=this_device_name,
                )

                # 🔹 Resolve canonical DB device
                result = await db.execute(
                    select(Device).where(
                        Device.user_uuid == uuid_obj,
                        Device.device_id == this_device_id
                    )
                )
                db_device = result.scalars().first()
                if not db_device:
                    raise RuntimeError(
                        f"Device {this_device_id} not found in DB for user {uuid_obj}"
                    )

                this_device_uuid = db_device.device_uuid
                this_device_name = db_device.device_name

                queue = await self.add_client(uuid_obj, this_device_uuid, this_device_name)

                # Load state
                state = await service.get_state(uuid_obj, device)

                initial_payload = {
                    "rev": 1,
                    "type": "timeline",
                    "ts": int(asyncio.get_running_loop().time() * 1000),
                    "this_device_uuid": str(this_device_uuid),
                    "this_device_name": this_device_name,
                }

                if state.now_playing:
                    initial_payload["now_playing"] = {
                        "track_uuid": str(state.now_playing.track.track_uuid),
                        "title": state.now_playing.track.name,
                        "artist": (
                            state.now_playing.track.artists[0].name
                            if state.now_playing.track.artists
                            else "—"
                        ),
                        "album": (
                            state.now_playing.track.albums[0].title
                            if state.now_playing.track.albums
                            else "—"
                        ),
                        "duration_ms": state.now_playing.duration_ms,
                        "file_url": state.now_playing.file_url,
                        "position_ms": 0,
                    }
                    initial_payload["play_state"] = "paused"

                # 🔹 Active device snapshot from DB, not just memory
                result = await db.execute(
                    select(PlaybackSession.active_device_uuid)
                    .where(PlaybackSession.user_uuid == uuid_obj)
                    .where(PlaybackSession.ended_at.is_(None))
                    .order_by(PlaybackSession.started_at.desc())
                )
                active_device_uuid = result.scalars().first()

                initial_payload["active_device_uuid"] = (
                    str(active_device_uuid) if active_device_uuid else None
                )

                redis_key = f"us:active_devices:{uuid_obj}"
                raw_devices = await redis_dep.redis_client.hgetall(redis_key)

                devices = []
                for dev_uuid, payload in raw_devices.items():
                    try:
                        meta = json.loads(payload)
                    except Exception:
                        logger.warning(f"⚠️ Corrupt device meta in Redis for {uuid_obj}/{dev_uuid}: {payload}")
                        continue

                    if meta.get("connected"):
                        devices.append({
                            "device_uuid": dev_uuid.decode() if isinstance(dev_uuid, bytes) else str(dev_uuid),
                            "device_name": meta.get("name"),
                            "connected": True,
                        })

                initial_payload["devices"] = devices

                yield f"{json.dumps(jsonable_encoder(initial_payload))}\n\n"
            finally:
                await db_gen.aclose()
        except Exception as e:
            logger.error(f"❌ Failed to send initial snapshot for {user_uuid}: {e}")
            return

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=5)

                    if isinstance(message, dict):
                        msg_copy = copy.deepcopy(message)
                        msg_copy["this_device_uuid"] = str(this_device_uuid)
                        msg_copy["this_device_name"] = this_device_name

                        # Normalize devices_changed → devices
                        if msg_copy.get("type") == "devices_changed":
                            msg_copy["type"] = "devices"

                        # 🔹 Always resolve active_device_uuid from DB
                        result = await db.execute(
                            select(PlaybackSession.active_device_uuid)
                            .where(PlaybackSession.user_uuid == uuid_obj)
                            .where(PlaybackSession.ended_at.is_(None))
                            .order_by(PlaybackSession.started_at.desc())
                        )
                        active_device_uuid = result.scalars().first()

                        msg_copy["active_device_uuid"] = (
                            str(active_device_uuid) if active_device_uuid else None
                        )

                        redis_key = f"us:active_devices:{uuid_obj}"
                        raw_devices = await redis_dep.redis_client.hgetall(redis_key)

                        devices = []
                        for dev_uuid, payload in raw_devices.items():
                            try:
                                meta = json.loads(payload)
                            except Exception:
                                logger.warning(f"⚠️ Corrupt device meta in Redis for {uuid_obj}/{dev_uuid}: {payload}")
                                continue

                            if meta.get("connected"):
                                devices.append({
                                    "device_uuid": dev_uuid.decode() if isinstance(dev_uuid, bytes) else str(dev_uuid),
                                    "device_name": meta.get("name"),
                                    "connected": True,
                                })

                        msg_copy["devices"] = devices

                        yield f"{json.dumps(jsonable_encoder(msg_copy))}\n\n"
                except asyncio.TimeoutError:
                    yield ":\n\n"
        finally:
            await self.remove_client(uuid_obj, this_device_uuid)

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

                        # fan-out to all connected device queues for this user
                        for (u, d), q in list(self._queues.items()):
                            if u != user_uuid:
                                continue
                            if q.full():
                                dropped = q.get_nowait()
                                logger.warning(f"⚠️ Queue full for {user_uuid}/{d}, dropped: {dropped}")
                            await q.put(data)
                            logger.info(f"➡️ Enqueued SSE for {user_uuid}/{d}: {data}")

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
    """Periodically publish playback heartbeats for all active sessions.
    Uses a Redis lock so only one worker runs this loop at a time.
    """
    lock_key = "heartbeat_lock"
    lock_ttl = 10  # seconds

    while True:
        try:
            if redis_dep.redis_client is None:
                await asyncio.sleep(5)
                continue

            # Try to acquire lock
            got_lock = await redis_dep.redis_client.set(
                lock_key,
                "1",
                ex=lock_ttl,
                nx=True,  # only set if not exists
            )

            if got_lock:
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
        await redis_sse_service._cleanup_stale_devices()




# Singleton instance
redis_sse_service = RedisSSEService()
