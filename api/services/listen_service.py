# services/listen_service.py

import logging
from datetime import datetime
from typing import Optional, List

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.sqlmodels import PlaybackHistory, User

logger = logging.getLogger(__name__)


class ListenService:
    """Service for recording and retrieving playback history (scrobbles)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- record listen --------------------------------------------------------
    async def add_listen(
        self,
        user: User,
        track_version_uuid,
        device_uuid,
        played_at: Optional[datetime] = None,
    ) -> PlaybackHistory:
        """
        Insert a new listen (scrobble) into PlaybackHistory.
        Assumes track/album/device are already resolved upstream.
        """
        history = PlaybackHistory(
            user_uuid=user.user_uuid,
            track_version_uuid=track_version_uuid,
            device_uuid=device_uuid,
            played_at=played_at or datetime.utcnow(),
        )

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        logger.info(
            f"🎧 Added listen user={user.username} "
            f"track_version={track_version_uuid} "
            f"device={device_uuid} at {history.played_at}"
        )
        return history

    # --- queries --------------------------------------------------------------
    async def get_recent_listens(
        self, user: User, limit: int = 50
    ) -> List[PlaybackHistory]:
        """Return the most recent listens for a user."""
        stmt = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
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
