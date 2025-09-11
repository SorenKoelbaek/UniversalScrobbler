# services/listen_service.py

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from models.appmodels import RecommendedArtist

from models.sqlmodels import PlaybackHistory, User, TrackVersion, Album, Track, SimilarArtistBridge, TrackArtistBridge, Artist
from services.listenbrainz_service import ListenBrainzService
logger = logging.getLogger(__name__)
import asyncio

class ListenService:
    """Service for recording and retrieving playback history (scrobbles)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.lb_service = ListenBrainzService(db)
    # --- record listen --------------------------------------------------------
    async def add_listen(
            self,
            user: User,
            track_version_uuid: UUID,
            device_uuid: UUID,
            played_at: Optional[datetime] = None,
    ) -> PlaybackHistory:
        # fetch TrackVersion so we can resolve track + album + artists
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

        # grab the first linked album (or None)
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
            played_at=played_at or datetime.utcnow(),
        )

        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)

        logger.info(
            f"🎧 Added listen user={user.username} track_version={track_version_uuid} "
            f"track={track_version.track_uuid} album={album_uuid} device={device_uuid}"
        )

        # --- trigger similar artist caching inline ---
        for artist in track_version.track.artists:
            if not artist.musicbrainz_artist_id:
                continue

            asyncio.create_task(
                self.lb_service.get_or_create_similar_artists(artist.artist_uuid)
            )

        return history

    # --- queries --------------------------------------------------------------
    async def get_recent_listens(
            self, user: User, days: int = 7
    ) -> List[PlaybackHistory]:
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
                weight_subq.c.track_uuid == TrackArtistBridge.track_uuid
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
                artist_weight_subq.c.reference_artist_uuid == SimilarArtistBridge.reference_artist_uuid,
            )
            .group_by(SimilarArtistBridge.artist_uuid)
            .order_by(func.sum(artist_weight_subq.c.weight * SimilarArtistBridge.score).desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # fetch artist details
        artist_uuids = [r[0] for r in rows if r[0] is not None]
        if not artist_uuids:
            return []

        stmt = select(Artist).where(Artist.artist_uuid.in_(artist_uuids))
        res = await self.db.execute(stmt)
        artist_map = {a.artist_uuid: a for a in res.scalars().all()}

        # build proper models
        return [
            RecommendedArtist(
                **artist_map[artist_uuid].__dict__,
                score=float(total_score),
            )
            for artist_uuid, total_score in rows
            if artist_uuid in artist_map
        ]