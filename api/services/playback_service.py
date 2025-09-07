# services/playback_service.py
import json
import time
import logging
from uuid import UUID
from datetime import datetime, timezone, UTC

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select, delete
from redis.asyncio import Redis

from models.sqlmodels import (
    PlaybackQueue,
    PlaybackSession,
    CollectionTrack,
    TrackVersion,
    Album,
    Artist,
    Track,
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

    async def _get_or_create_session(self, user_uuid: UUID) -> PlaybackSession:
        """Ensure there is a PlaybackSession row for this user."""
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
        return session

    async def resume(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Resume playback without altering the queue."""
        session = await self._get_or_create_session(user_uuid)
        session.play_state = "playing"
        session.updated_at = datetime.utcnow()
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, event_type="timeline", rev=1)
        logger.info(f"▶️ Resumed playback for {user_uuid}")
        return await self._get_queue(user_uuid)

    async def pause(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Pause playback and persist state."""
        session = await self._get_or_create_session(user_uuid)
        session.play_state = "paused"
        session.updated_at = datetime.utcnow()
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        logger.info(f"⏸️ Paused playback for {user_uuid}")
        return await self._get_queue(user_uuid)

    async def _publish(self, user_uuid: UUID, event_type: str, rev: int = 1):
        """Publish a delta event to Redis SSE channel.
        For timeline updates, enrich with now_playing snapshot.
        """
        base_payload = {
            "rev": rev,
            "type": event_type,
            "ts": int(time.time() * 1000),
        }

        if event_type == "timeline":
            # Grab current queue state
            state = await self._get_queue(user_uuid)

            # Grab persisted session
            result = await self.db.execute(
                select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
            )
            session = result.scalars().first()

            if state.now_playing:
                base_payload["now_playing"] = {
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
                    "position_ms": session.position_ms if session else 0,
                }
                base_payload["play_state"] = (
                    session.play_state if session else "paused"
                )

        channel = f"us:user:{user_uuid}"
        await self.redis.publish(channel, json.dumps(base_payload))
        logger.info(
            f"📡 Published event={event_type} rev={rev} user={user_uuid} "
            f"channel={channel} payload={base_payload}"
        )

    async def _get_queue(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Hydrate the current queue + now playing for user, including file/duration."""
        stmt = (
            select(PlaybackQueue, CollectionTrack)
            .join(
                CollectionTrack,
                CollectionTrack.track_version_uuid == PlaybackQueue.track_version_uuid,
            )
            .where(PlaybackQueue.user_uuid == user_uuid)
            .options(
                selectinload(PlaybackQueue.track_version)
                .selectinload(TrackVersion.track)
                .selectinload(Track.artists),
                selectinload(PlaybackQueue.track_version)
                .selectinload(TrackVersion.track)
                .selectinload(Track.albums)
                .selectinload(Album.types),
                selectinload(PlaybackQueue.track_version).selectinload(
                    TrackVersion.album_releases
                ),
            )
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()  # each row is (PlaybackQueue, CollectionTrack)

        items: list[PlaybackQueueItem] = []
        now_playing, next_item, prev_item = None, None, None

        for idx, (row, ctrack) in enumerate(rows):
            track = row.track_version.track
            item = PlaybackQueueItem(
                playback_queue_uuid=row.playback_queue_uuid,
                user_uuid=row.user_uuid,
                track=TrackReadSimple.model_validate(track),
                position=row.position,
                added_at=row.added_at,
                added_by=row.added_by,
                played=row.played,
                skipped=row.skipped,
                duration_ms=ctrack.duration_ms,
                file_url=f"/music/file/{ctrack.collection_track_uuid}",
            )
            items.append(item)

            if not row.played and not row.skipped and now_playing is None:
                now_playing = item
                prev_item = items[idx - 1] if idx > 0 else None

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

    async def get_state(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Return the current playback state for a user."""
        return await self._get_queue(user_uuid)

    async def play(self, user_uuid: UUID, body: PlayRequest) -> PlaybackQueueSimple:
        """Play a track/album/artist by enqueueing and marking it as now playing."""
        # Clear existing queue to avoid position conflicts
        await self.db.execute(
            delete(PlaybackQueue).where(PlaybackQueue.user_uuid == user_uuid)
        )

        position = 0
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
                position=position,
                added_at=datetime.utcnow(),
                added_by="user",
            )
            self.db.add(pq)
            new_items.append(pq)

        elif body.album_uuid:
            stmt = (
                select(TrackVersion)
                .join(TrackVersion.album_releases)
                .where(Album.album_uuid == body.album_uuid)
            )
            result = await self.db.execute(stmt)
            for idx, tv in enumerate(result.scalars().all()):
                pq = PlaybackQueue(
                    user_uuid=user_uuid,
                    track_version_uuid=tv.track_version_uuid,
                    position=idx,
                    added_at=datetime.utcnow(),
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
                    position=idx,
                    added_at=datetime.utcnow(),
                    added_by="artist",
                )
                self.db.add(pq)
                new_items.append(pq)

        await self.db.commit()
        logger.info(f"▶️ Enqueued {len(new_items)} items for {user_uuid}")

        await self._publish(user_uuid, "timeline")
        return await self._get_queue(user_uuid)

    async def next(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Mark current as played and advance to next."""
        stmt = (
            select(PlaybackQueue)
            .where(
                PlaybackQueue.user_uuid == user_uuid,
                PlaybackQueue.played == False,
                PlaybackQueue.skipped == False,
            )
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        current = result.scalars().first()
        if current:
            current.played = True
            self.db.add(current)
            await self.db.commit()

        await self._publish(user_uuid, "timeline")
        return await self._get_queue(user_uuid)

    async def previous(self, user_uuid: UUID) -> PlaybackQueueSimple:
        """Go back to previous track (mark current as skipped, replay previous)."""
        stmt = (
            select(PlaybackQueue)
            .where(
                PlaybackQueue.user_uuid == user_uuid,
                PlaybackQueue.played == False,
                PlaybackQueue.skipped == False,
            )
            .order_by(PlaybackQueue.position.asc())
        )
        result = await self.db.execute(stmt)
        current = result.scalars().first()
        if current:
            current.skipped = True
            self.db.add(current)
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
            position_ms=session.position_ms if session else 0,
            play_state=session.play_state if session else "paused",
        ).model_dump()

    async def seek(self, user_uuid: UUID, position_ms: int) -> PlaybackQueueSimple:
        session = await self._get_or_create_session(user_uuid)
        session.position_ms = position_ms
        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        await self.db.commit()

        await self._publish(user_uuid, "timeline")
        logger.info(f"⏩ Seeked playback for {user_uuid} → {position_ms}ms")
        return await self._get_queue(user_uuid)

