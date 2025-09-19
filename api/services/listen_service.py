# services/listen_service.py

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
import asyncio

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from dependencies.database import async_session

from models.appmodels import RecommendedArtist
from models.sqlmodels import (
    PlaybackHistory,
    User,
    TrackVersion,
    Album,
    Track,
    SimilarArtistBridge,
    TrackArtistBridge,
    Artist,
)
from services.listenbrainz_service import ListenBrainzService

logger = logging.getLogger(__name__)


class ListenService:
    """Service for recording and retrieving playback history (scrobbles)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.lb_service = ListenBrainzService()

    # --- record listen --------------------------------------------------------
    async def add_listen(
        self,
        user: User,
        track_version_uuid: UUID,
        device_uuid: UUID,
        session_uuid: UUID | None = None,
        played_at: Optional[datetime] = None,
    ) -> PlaybackHistory:
        stmt = (
            select(TrackVersion)
            .where(TrackVersion.track_version_uuid == track_version_uuid)
            .options(
                selectinload(TrackVersion.track).selectinload(Track.artists),
                selectinload(TrackVersion.track).selectinload(Track.albums),
            )
        )
        result = await self.db.execute(stmt)
        track_version = result.scalar_one()

        album_uuid = (
            track_version.track.albums[0].album_uuid
            if track_version.track.albums
            else None
        )

        history = PlaybackHistory(
            user_uuid=user.user_uuid,
            track_version_uuid=track_version_uuid,
            track_uuid=track_version.track_uuid,
            album_uuid=album_uuid,
            device_uuid=device_uuid,
            session_uuid=session_uuid,
            played_at=played_at or datetime.utcnow(),
        )

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        logger.info(
            f"🎧 Added listen user={user.username} "
            f"track_version={track_version_uuid} track={track_version.track_uuid} "
            f"album={album_uuid} device={device_uuid} session={session_uuid}"
        )

        # run similar-artist caching in background with a fresh session
        async def run_similar_fetch(artist_uuid: UUID):
            async with async_session() as new_db:
                lb_service = ListenBrainzService()
                await lb_service.get_or_create_similar_artists(artist_uuid, new_db)

        for artist in track_version.track.artists:
            if artist.musicbrainz_artist_id:
                asyncio.create_task(run_similar_fetch(artist.artist_uuid))

        return history

    # --- queries --------------------------------------------------------------
    async def get_recent_listens(self, user: User, days: int = 7) -> List[PlaybackHistory]:
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.played_at >= since)
            .options(
                selectinload(PlaybackHistory.track),
                selectinload(PlaybackHistory.album).selectinload(Album.artists),
            )
            .order_by(PlaybackHistory.played_at.desc())
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

    async def get_user_recommended_artists(
        self, user_uuid: UUID, limit: int = 15, days: int = 7
    ) -> list[RecommendedArtist]:
        since = datetime.utcnow() - timedelta(days=days)

        # subquery: weight per listened artist (last N days)
        weight_subq = (
            select(
                PlaybackHistory.track_uuid,
                func.count(PlaybackHistory.playback_history_uuid).label("weight"),
            )
            .where(PlaybackHistory.user_uuid == user_uuid)
            .where(PlaybackHistory.played_at >= since)
            .group_by(PlaybackHistory.track_uuid)
            .subquery()
        )

        # join Track → Artist (via TrackArtistBridge)
        artist_weight_subq = (
            select(
                TrackArtistBridge.artist_uuid.label("reference_artist_uuid"),
                func.sum(weight_subq.c.weight).label("weight"),
            )
            .join(
                TrackArtistBridge,
                weight_subq.c.track_uuid == TrackArtistBridge.track_uuid,
            )
            .group_by(TrackArtistBridge.artist_uuid)
            .subquery()
        )

        # join SimilarArtistBridge
        stmt = (
            select(
                SimilarArtistBridge.artist_uuid,
                func.sum(
                    artist_weight_subq.c.weight * SimilarArtistBridge.score
                ).label("total_score"),
            )
            .join(
                artist_weight_subq,
                artist_weight_subq.c.reference_artist_uuid
                == SimilarArtistBridge.reference_artist_uuid,
            )
            .group_by(SimilarArtistBridge.artist_uuid)
            .order_by(
                func.sum(artist_weight_subq.c.weight * SimilarArtistBridge.score).desc()
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # fetch artist details WITH relationships
        artist_uuids = [r[0] for r in rows if r[0] is not None]
        if not artist_uuids:
            return []

        stmt = (
            select(Artist)
            .options(
                selectinload(Artist.albums).selectinload(Album.releases),
                selectinload(Artist.albums).selectinload(Album.tags),
                selectinload(Artist.albums).selectinload(Album.types),
                selectinload(Artist.album_releases),
                selectinload(Artist.tags),
            )
            .where(Artist.artist_uuid.in_(artist_uuids))
            .execution_options(populate_existing=True)
        )
        res = await self.db.execute(stmt)
        artist_map = {a.artist_uuid: a for a in res.scalars().all()}

        return [
            RecommendedArtist(
                **artist_map[artist_uuid].__dict__,
                score=float(total_score),
            )
            for artist_uuid, total_score in rows
            if artist_uuid in artist_map
        ]
