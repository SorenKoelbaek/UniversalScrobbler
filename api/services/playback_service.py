# services/playback_service.py
import json
import time
import logging
from uuid import UUID
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class PlaybackService:
    """
    Service for managing playback state and publishing events over Redis.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_state(self, user_uuid: UUID) -> dict:
        """
        Return the current playback state for a user.
        For now, this is a placeholder — in future we can fetch from Redis or DB.
        """
        # TODO: Later: restore last known state from Redis (e.g. HGETALL).
        state = {
            "user_uuid": str(user_uuid),
            "track_uuid": None,
            "position_ms": 0,
            "play_state": "paused",
            "last_update_mono": int(time.time() * 1000),
            "revision": 1,
        }
        logger.debug(f"get_state for {user_uuid}: {state}")
        return state

    async def play_track(self, user_uuid: UUID, track_uuid: str) -> dict:
        payload = {
            "rev": 1,
            "type": "play",
            "track_uuid": track_uuid,
            "ts": int(time.time() * 1000),
        }
        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(payload))
        logger.info(f"▶️ Play track {track_uuid} for {user_uuid} via {channel}")
        return payload

    async def pause(self, user_uuid: UUID) -> dict:
        payload = {
            "rev": 1,
            "type": "pause",
            "ts": int(time.time() * 1000),
        }
        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(payload))
        logger.info(f"⏸️ Pause for {user_uuid} via {channel}")
        return payload

    async def next(self, user_uuid: UUID) -> dict:
        payload = {
            "rev": 1,
            "type": "next",
            "ts": int(time.time() * 1000),
        }
        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(payload))
        logger.info(f"⏭️ Next track for {user_uuid} via {channel}")
        return payload

    async def previous(self, user_uuid: UUID) -> dict:
        payload = {
            "rev": 1,
            "type": "previous",
            "ts": int(time.time() * 1000),
        }
        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(payload))
        logger.info(f"⏮️ Previous track for {user_uuid} via {channel}")
        return payload
