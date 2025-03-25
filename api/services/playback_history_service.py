from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from typing import List, Optional
from collections import Counter
from models.sqlmodels import PlaybackHistory, User
from models.appmodels import PlaybackHistoryRead, CurrentlyPlaying


class PlaybackHistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_playback_history(self, user: User, days: int = 7) -> List[PlaybackHistoryRead]:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)

        statement = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.played_at >= since)
            .where(PlaybackHistory.full_play)
            .order_by(PlaybackHistory.played_at.desc())
        )

        result = await self.db.exec(statement)
        return result.all()

    async def get_top_tracks(self, user: User, days: int = 7):
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)

        statement = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.played_at >= since)
            .where(PlaybackHistory.full_play)
        )

        result = await self.db.exec(statement)
        results = result.all()

        play_counter = Counter(
            (r.track_name, r.artist_name, r.album_name)
            for r in results
        )

        top_tracks = [
            {
                "track_name": t[0],
                "artist_name": t[1],
                "album_name": t[2],
                "play_count": count
            }
            for t, count in play_counter.most_common(10)
        ]

        return top_tracks

    async def get_currently_playing(self, user: User) -> Optional[CurrentlyPlaying]:
        statement = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .order_by(PlaybackHistory.played_at.desc())
            .limit(1)
        )

        result = await self.db.exec(statement)
        record = result.first()

        if not record:
            return None

        duration = record.duration_ms or 0
        progress = record.progress_ms or 0
        time_since_play = (datetime.utcnow() - record.played_at).total_seconds() * 1000
        is_playing = time_since_play < (duration + 1000)

        return CurrentlyPlaying(
            spotify_track_id=record.spotify_track_id,
            track_name=record.track_name,
            artist_name=record.artist_name,
            album_name=record.album_name,
            discogs_release_id=record.discogs_release_id,
            played_at=record.played_at,
            source=record.source,
            device_name=record.device_name,
            duration_ms=record.duration_ms,
            progress_ms=record.progress_ms,
            is_still_playing=is_playing
        )

    async def get_current_play_message(self, user: User) -> dict:
        current_play: Optional[CurrentlyPlaying] = await self.get_currently_playing(user)
        return {
            "type": "current_play",
            "data": current_play.model_dump(mode="json") if current_play else None
        }