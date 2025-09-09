# services/listen_service.py

import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from models.sqlmodels import PlaybackHistory, User, TrackVersion, Album, Artist

logger = logging.getLogger(__name__)


class ListenService:
    """Service for recording and retrieving playback history (scrobbles)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- record listen --------------------------------------------------------
    async def add_listen(
            self,
            user: User,
            track_version_uuid: UUID,
            device_uuid: UUID,
            played_at: Optional[datetime] = None,
    ) -> PlaybackHistory:
        # fetch TrackVersion so we can resolve track + album
        stmt = (
            select(TrackVersion)
            .where(TrackVersion.track_version_uuid == track_version_uuid)
            .options(
                selectinload(TrackVersion.track),
                selectinload(TrackVersion.track).selectinload(Track.albums),
            )
        )
        result = await self.db.execute(stmt)
        track_version = result.scalar_one()

        # grab the first linked album (or None)
        album_uuid = track_version.track.albums[0].album_uuid if track_version.track.albums else None

        history = PlaybackHistory(
            user_uuid=user.user_uuid,
            track_version_uuid=track_version_uuid,
            track_uuid=track_version.track_uuid,
            album_uuid=album_uuid,
            device_uuid=device_uuid,
            played_at=played_at or datetime.utcnow(),
        )

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        logger.info(
            f"🎧 Added listen user={user.username} track_version={track_version_uuid} "
            f"track={track_version.track_uuid} album={album_uuid} device={device_uuid}"
        )
        return history

    # --- queries --------------------------------------------------------------
    async def get_recent_listens(
            self, user: User, limit: int = 50
    ) -> List[PlaybackHistory]:
        stmt = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .options(
                selectinload(PlaybackHistory.track),
                selectinload(PlaybackHistory.album).selectinload(Album.artists),
            )
            .order_by(PlaybackHistory.played_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_listens_between(
        self, user: User, start: datetime, end: datetime
    ) -> List[PlaybackHistory]:
        """Return listens in a given date range."""
        stmt = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.played_at >= start)
            .where(PlaybackHistory.played_at < end)
            .order_by(PlaybackHistory.played_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
