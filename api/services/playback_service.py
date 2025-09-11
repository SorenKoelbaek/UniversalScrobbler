import json
import time
import logging
from uuid import UUID
from datetime import datetime, UTC

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlmodel import select, delete
from redis.asyncio import Redis
from services.listen_service import ListenService
from models.sqlmodels import (
    PlaybackQueue,
    PlaybackSession,
    LibraryTrack,   # 🔄 replaced CollectionTrack
    TrackVersion,
    Album,
    Artist,
    Track,
    AlbumRelease,
    PlaybackHistory,
    User
)
from models.appmodels import (
    PlayRequest,
    PlaybackQueueSimple,
    PlaybackQueueItem,
    TrackReadSimple,
    NowPlayingEvent,
)

logger = logging.getLogger(__name__)


class PlaybackService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.listen_service = ListenService(db)
    # --- helpers --------------------------------------------------------------

    def _should_register_play(self, position_ms: int, duration_ms: int | None) -> bool:
        """Return True if thresholds are met (≥50% or ≥240s)."""
        if not duration_ms:
            return False

        threshold_50pct = duration_ms * 0.5
        threshold_240s = 240_000
        return position_ms >= min(threshold_50pct, threshold_240s)

    async def _register_play_if_needed(self, user_uuid: UUID, device: dict | None = None):
        """Check current track for eligibility and log if not already recorded."""
        session = await self._get_or_create_session(user_uuid)
        state = await self._get_queue(user_uuid)
        if not state.now_playing or session.current_registered:
            return

        queue_entry_id = state.now_playing.playback_queue_uuid
        result = await self.db.execute(
            select(PlaybackQueue)
            .where(PlaybackQueue.playback_queue_uuid == queue_entry_id)
            .options(
                selectinload(PlaybackQueue.track_version)
                .selectinload(TrackVersion.track)
            )
        )
        pq = result.scalars().first()
        if not pq:
            return

        track_version = pq.track_version
        track = track_version.track
        user = await self.db.get(User, user_uuid)

        # 🔹 Ensure we have a valid device before scrobble
        if not session.active_device_uuid:
            if device:
                session.active_device_uuid = await self._ensure_device(user_uuid, device)
                logger.info(
                    f"_register_play_if_needed: claimed device {session.active_device_uuid} "
                    f"for user={user_uuid} because session had none"
                )
            else:
                logger.warning(
                    f"_register_play_if_needed: no active device for user={user_uuid}, skipping scrobble"
                )
                return

        # ✅ Insert playback history
        await self.listen_service.add_listen(
            user=user,
            track_version_uuid=track_version.track_version_uuid,
            device_uuid=session.active_device_uuid,
            played_at=datetime.now(UTC),
        )

        session.current_registered = True
        self.db.add(session)
        await self.db.commit()

        logger.info(
            f"✅ Registered play track={track.name} "
            f"user={user_uuid} device={session.active_device_uuid}"
        )

    def _project_position(self, session: PlaybackSession) -> int:
        if not session or session.play_state != "playing":
            return session.position_ms
        elapsed_ms = int((datetime.now(UTC) - session.updated_at).total_seconds() * 1000)
        return session.position_ms + elapsed_ms

    async def _get_or_create_session(
            self,
            user_uuid: UUID,
            device_id: str | None = None,
            device_name: str | None = None,
    ) -> PlaybackSession:
        result = await self.db.execute(
            select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
        )
        session = result.scalars().first()

        if not session:
            session = PlaybackSession(user_uuid=user_uuid)
            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            logger.debug(f"✨ Created new PlaybackSession for {user_uuid}")

        if device_id:
            from services.device_service import DeviceService
            device_service = DeviceService(self.db)
            device = await device_service.get_or_create_device(
                user_uuid=user_uuid,
                device_id=device_id,
                device_name=device_name or "Unknown Device",
            )

            from services.redis_sse_service import redis_sse_service
            active_devices = redis_sse_service._active_devices.get(user_uuid, {})

            if not session.active_device_uuid or str(session.active_device_uuid) not in active_devices:
                session.active_device_uuid = device.device_uuid
                self.db.add(session)
                await self.db.commit()
                await self.db.refresh(session)
                logger.info(
                    f"🔄 Active device set to {device.device_uuid} ({device.device_name}) for {user_uuid}"
                )

        return session

    # --- controls -------------------------------------------------------------

    async def resume(self, user_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        session.position_ms = self._project_position(session)
        session.play_state = "playing"
        session.updated_at = datetime.now(UTC)
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, event_type="timeline", rev=1)
        logger.info(f"▶️ Resumed playback for {user_uuid}")
        return await self._get_queue(user_uuid)

    async def pause(self, user_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        session.position_ms = self._project_position(session)
        session.play_state = "paused"
        session.updated_at = datetime.now(UTC)
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        logger.info(f"⏸️ Paused playback for {user_uuid}")
        return await self._get_queue(user_uuid)

    async def seek(self, user_uuid: UUID, position_ms: int, device: dict | None = None) -> PlaybackQueueSimple:
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        session.position_ms = position_ms
        session.updated_at = datetime.now(UTC)
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        logger.info(f"⏩ Seeked playback for {user_uuid} → {position_ms}ms")
        return await self._get_queue(user_uuid)

    # --- publishing -----------------------------------------------------------

    async def _publish(self, user_uuid: UUID, event_type: str, rev: int = 1):
        base_payload = {"rev": rev, "type": event_type, "ts": int(time.time() * 1000)}

        if event_type == "timeline":
            state = await self._get_queue(user_uuid)
            result = await self.db.execute(
                select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
            )
            session = result.scalars().first()

            if state.now_playing and session:
                track = state.now_playing.track
                album = track.albums[0] if track.albums else None

                base_payload["now_playing"] = {
                    "track_uuid": str(track.track_uuid),
                    "title": track.name,
                    "artist": (
                        track.artists[0].name if track.artists else "—"
                    ),
                    "album": album.title if album else "—",
                    "duration_ms": state.now_playing.duration_ms,
                    "file_url": state.now_playing.file_url,
                    "position_ms": self._project_position(session),
                }
                base_payload["play_state"] = session.play_state

        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(base_payload))
        logger.info(
            f"📡 Published event={event_type} rev={rev} user={user_uuid} "
            f"channel={channel} payload={base_payload}"
        )

    async def _publish_heartbeat(self, user_uuid: UUID):
        session = await self._get_or_create_session(user_uuid)

        payload = {
            "rev": 0,
            "type": "heartbeat",
            "ts": int(time.time() * 1000),
            "position_ms": self._project_position(session),
            "play_state": session.play_state,
            "active_device_uuid": str(session.active_device_uuid) if session.active_device_uuid else None,
        }

        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(payload))
        logger.debug(f"💓 Heartbeat for {user_uuid}: {payload}")
    # --- queue handling -------------------------------------------------------

    async def _get_queue(self, user_uuid: UUID) -> PlaybackQueueSimple:
        stmt = (
            select(PlaybackQueue, LibraryTrack)
            .join(LibraryTrack, LibraryTrack.track_version_uuid == PlaybackQueue.track_version_uuid)
            .where(PlaybackQueue.user_uuid == user_uuid)
            .options(
                selectinload(PlaybackQueue.track_version).selectinload(TrackVersion.track).selectinload(Track.artists),
                selectinload(PlaybackQueue.track_version).selectinload(TrackVersion.track).selectinload(
                    Track.albums).selectinload(Album.types),
                selectinload(PlaybackQueue.track_version).selectinload(TrackVersion.album_releases),
            )
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        # load session to check anchored now_playing
        session = await self._get_or_create_session(user_uuid)

        items: list[PlaybackQueueItem] = []
        now_playing, next_item, prev_item = None, None, None

        for idx, (row, ltrack) in enumerate(rows):
            track = row.track_version.track
            item = PlaybackQueueItem(
                playback_queue_uuid=row.playback_queue_uuid,
                user_uuid=row.user_uuid,
                track=TrackReadSimple.model_validate(track),
                position=row.position,
                added_at=row.added_at,
                added_by=row.added_by,
                duration_ms=ltrack.duration_ms,
                file_url=f"/music/file/{ltrack.library_track_uuid}",  # 🔄 now points to LibraryTrack
            )
            items.append(item)

            if row.playback_queue_uuid == session.current_queue_uuid:
                now_playing = item
                prev_item = items[idx - 1] if idx > 0 else None

        # fallback if no anchor
        if not now_playing and items:
            now_playing = items[0]

        if now_playing:
            idx = items.index(now_playing)
            if idx + 1 < len(items):
                next_item = items[idx + 1]

        return PlaybackQueueSimple(
            playback_queue_uuid=rows[0][0].playback_queue_uuid if rows else UUID(int=0),
            user_uuid=user_uuid,
            tracks=items,
            now_playing=now_playing,
            next=next_item,
            previous=prev_item,
        )

    async def get_state(self, user_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        state = await self._get_queue(user_uuid)

        result = await self.db.execute(
            select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
        )
        session = result.scalars().first()

        if session:
            from services.redis_sse_service import redis_sse_service
            active_devices = redis_sse_service._active_devices.get(user_uuid, {})

            # --- clear ghost devices ---
            if session.active_device_uuid and str(session.active_device_uuid) not in active_devices:
                logger.warning(
                    f"get_state: clearing ghost active device {session.active_device_uuid} "
                    f"for user={user_uuid} (known devices: {list(active_devices.keys())})"
                )
                if device:
                    session.active_device_uuid = await self._ensure_device(user_uuid, device)
                else:
                    session.active_device_uuid = None

            # --- auto-claim if no active device ---
            if not session.active_device_uuid and device:
                claimed_uuid = await self._ensure_device(user_uuid, device)
                session.active_device_uuid = claimed_uuid
                logger.info(
                    f"get_state: no active device, assigning {claimed_uuid} "
                    f"({device['device_name']}) for user={user_uuid}"
                )

            # --- expire stale sessions ---
            max_age_seconds = 300  # 5 minutes
            age = (datetime.now(UTC) - session.updated_at).total_seconds()
            if age > max_age_seconds and session.play_state == "playing":
                logger.info(
                    f"get_state: session for {user_uuid} expired after {age:.0f}s, forcing pause"
                )
                session.play_state = "paused"
                session.position_ms = 0

            self.db.add(session)
            await self.db.commit()

        return state

    async def _ensure_device(self, user_uuid: UUID, device: dict) -> UUID:
        """Make sure the device exists in DB and return its UUID."""
        from services.device_service import DeviceService
        device_service = DeviceService(self.db)
        dev = await device_service.get_or_create_device(
            user_uuid=user_uuid,
            device_id=device["device_id"],
            device_name=device["device_name"],
        )
        return dev.device_uuid

    async def play(self, user_uuid: UUID, body: PlayRequest, device: dict | None = None) -> PlaybackQueueSimple:
        """Replace queue with new track/album/artist and start playing."""
        # first, check if we need to add scrobble from "previous"
        await self._register_play_if_needed(user_uuid)
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        # Then clear session reference to avoid FK constraint error
        session.current_queue_uuid = None
        self.db.add(session)
        await self.db.flush()  # make sure the FK is cleared before queue delete

        # Now it’s safe to delete old queue
        await self.db.execute(
            delete(PlaybackQueue).where(PlaybackQueue.user_uuid == user_uuid)
        )

        # Enqueue new track(s)
        await self._enqueue(user_uuid, body, clear=False)

        # Refresh session with first track from queue
        state = await self._get_queue(user_uuid)
        first_track = state.tracks[0] if state.tracks else None

        session.position_ms = 0
        session.play_state = "playing"
        session.updated_at = datetime.now(UTC)
        session.current_registered = False
        session.current_queue_uuid = (
            first_track.playback_queue_uuid if first_track else None
        )

        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        return await self._get_queue(user_uuid)

    async def add_to_queue(self, user_uuid: UUID, body: PlayRequest) -> PlaybackQueueSimple:
        """Append track/album/artist to existing queue without altering playback."""
        logger.info(body)
        await self._enqueue(user_uuid, body, clear=False)
        await self._publish(user_uuid, "timeline")
        return await self._get_queue(user_uuid)

    async def jump_to(self, user_uuid: UUID, playback_queue_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        """Skip directly to a specific queue entry and resume playback."""
        await self._register_play_if_needed(user_uuid)
        # make sure this entry exists in the queue
        stmt = (
            select(PlaybackQueue)
            .where(
                PlaybackQueue.user_uuid == user_uuid,
                PlaybackQueue.playback_queue_uuid == playback_queue_uuid,
            )
        )
        result = await self.db.execute(stmt)
        entry = result.scalars().first()
        if not entry:
            raise ValueError(f"Queue entry {playback_queue_uuid} not found")

        # update session anchor
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        session.current_queue_uuid = playback_queue_uuid
        session.position_ms = 0
        session.play_state = "playing"
        session.updated_at = datetime.now(UTC)
        session.current_registered = False
        self.db.add(session)

        await self.db.commit()
        await self._publish(user_uuid, "timeline")
        logger.info(f"⏭️ Jumped to queue entry {playback_queue_uuid} for {user_uuid}")
        return await self._get_queue(user_uuid)

    async def _enqueue(self, user_uuid: UUID, body: PlayRequest, clear: bool = False):
        if clear:
            await self.db.execute(
                delete(PlaybackQueue).where(PlaybackQueue.user_uuid == user_uuid)
            )

        # find current max position
        result = await self.db.execute(
            select(PlaybackQueue.position).where(PlaybackQueue.user_uuid == user_uuid)
        )
        current_max = max([p for (p,) in result.all()], default=-1)
        base_position = current_max + 1

        new_items = []
        if body.track_uuid or body.track_version_uuid:
            track_version_uuid = body.track_version_uuid
            if not track_version_uuid:
                stmt = select(TrackVersion).where(
                    TrackVersion.track_uuid == body.track_uuid
                )
                result = await self.db.execute(stmt)
                track_version = result.scalars().first()
                if not track_version:
                    raise ValueError("Track not found")
                track_version_uuid = track_version.track_version_uuid

            pq = PlaybackQueue(
                user_uuid=user_uuid,
                track_version_uuid=track_version_uuid,
                position=base_position,
                added_at=datetime.now(UTC),
                added_by="user",
            )
            self.db.add(pq)
            new_items.append(pq)

        elif body.album_uuid:
            stmt = (
                select(TrackVersion)
                .join(TrackVersion.album_releases)
                .join(AlbumRelease.album)
                .where(Album.album_uuid == body.album_uuid)
                .options(joinedload(TrackVersion.track))
            )
            result = await self.db.execute(stmt)
            track_versions = result.scalars().all()
            for idx, tv in enumerate(track_versions):
                pq = PlaybackQueue(
                    user_uuid=user_uuid,
                    track_version_uuid=tv.track_version_uuid,
                    position=base_position + idx,
                    added_at=datetime.now(UTC),
                    added_by="album",
                )
                self.db.add(pq)
                new_items.append(pq)

        elif body.artist_uuid:
            stmt = (
                select(TrackVersion)
                .join(TrackVersion.track)
                .join(TrackVersion.track.artists)
                .where(Artist.artist_uuid == body.artist_uuid)
            )
            result = await self.db.execute(stmt)
            for idx, tv in enumerate(result.scalars().all()):
                pq = PlaybackQueue(
                    user_uuid=user_uuid,
                    track_version_uuid=tv.track_version_uuid,
                    position=base_position + idx,
                    added_at=datetime.now(UTC),
                    added_by="artist",
                )
                self.db.add(pq)
                new_items.append(pq)

        await self.db.commit()
        logger.info(f"➕ Added {len(new_items)} items to queue for {user_uuid}")

    async def next(self, user_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        """Advance to the next track in the queue (using current_queue_uuid)."""
        await self._register_play_if_needed(user_uuid)
        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        # fetch queue ordered
        stmt = (
            select(PlaybackQueue)
            .where(PlaybackQueue.user_uuid == user_uuid)
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return await self._get_queue(user_uuid)

        # find index of current
        try:
            idx = next(i for i, r in enumerate(rows) if r.playback_queue_uuid == session.current_queue_uuid)
        except StopIteration:
            idx = -1

        if idx + 1 < len(rows):  # move forward if possible
            session.current_queue_uuid = rows[idx + 1].playback_queue_uuid
            session.position_ms = 0
            session.play_state = "playing"
            session.updated_at = datetime.now(UTC)
            session.current_registered = False
            self.db.add(session)
            await self.db.commit()
            await self._publish(user_uuid, "timeline")

        return await self._get_queue(user_uuid)

    async def previous(self, user_uuid: UUID, device: dict | None = None) -> PlaybackQueueSimple:
        """Go back to the previous track in the queue (using current_queue_uuid)."""
        await self._register_play_if_needed(user_uuid)

        session = await self._get_or_create_session(user_uuid, device.get("device_id") if device else None, device.get("device_name") if device else None)
        # fetch queue ordered
        stmt = (
            select(PlaybackQueue)
            .where(PlaybackQueue.user_uuid == user_uuid)
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return await self._get_queue(user_uuid)

        # find index of current
        try:
            idx = next(i for i, r in enumerate(rows) if r.playback_queue_uuid == session.current_queue_uuid)
        except StopIteration:
            idx = len(rows)  # not set yet → jump to last

        if idx - 1 >= 0:  # move back if possible
            session.current_queue_uuid = rows[idx - 1].playback_queue_uuid
            session.position_ms = 0
            session.play_state = "playing"
            session.updated_at = datetime.now(UTC)
            session.current_registered = False
            self.db.add(session)
            await self.db.commit()
            await self._publish(user_uuid, "timeline")

        return await self._get_queue(user_uuid)

    async def _make_now_playing_event(self, user_uuid: UUID) -> dict | None:
        state = await self._get_queue(user_uuid)
        if not state.now_playing:
            return None
        result = await self.db.execute(
            select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
        )
        session = result.scalars().first()
        track = state.now_playing.track
        return NowPlayingEvent(
            track_uuid=track.track_uuid,
            track_name=track.name,
            artist_uuid=track.artists[0].artist_uuid if track.artists else None,
            artist_name=track.artists[0].name if track.artists else "—",
            album_uuid=track.albums[0].album_uuid if track.albums else None,
            album_name=track.albums[0].title if track.albums else "—",
            duration_ms=state.now_playing.duration_ms,
            file_url=state.now_playing.file_url,
            position_ms=self._project_position(session) if session else 0,
            play_state=session.play_state if session else "paused",
        ).model_dump()

    async def reorder(self, user_uuid: UUID, new_order: list[UUID]) -> PlaybackQueueSimple:
        new_order = [UUID(x) for x in new_order]
        stmt = select(PlaybackQueue).where(PlaybackQueue.user_uuid == user_uuid)
        result = await self.db.execute(stmt)
        rows = {row.playback_queue_uuid: row for row in result.scalars().all()}

        for pos, pq_uuid in enumerate(new_order):
            if pq_uuid in rows:
                rows[pq_uuid].position = pos + 1000
                self.db.add(rows[pq_uuid])
        await self.db.flush()  # flush but don’t commit yet

        for pos, pq_uuid in enumerate(new_order):
            if pq_uuid in rows:
                rows[pq_uuid].position = pos
                self.db.add(rows[pq_uuid])
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        return await self._get_queue(user_uuid)
