import uuid
from mimetypes import knownfiles

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from typing import List, Optional
from collections import Counter
from models.sqlmodels import PlaybackHistory, User, Track, Album, TrackVersion
from models.appmodels import PlaybackHistorySimple, CurrentlyPlaying, PlaybackUpdatePayload, ArtistBase, AlbumBase, \
    PaginatedResponse
from config import settings
import logging
from services.music_service import MusicService
from services.device_service import DeviceService
from services.websocket_service import WebSocketService

logger = logging.getLogger(__name__)

class PlaybackHistoryService:
    def __init__(self, db: AsyncSession, websocket_service: WebSocketService = None):
        self.db = db
        self.music_service = MusicService(db)
        self.device_service = DeviceService(db)
        self.websocket_service = websocket_service

    async def get_user_playback_history(
        self,
        user: User,
        offset: int = 0,
        limit: int = 100,
    ) -> PaginatedResponse[PlaybackHistorySimple]:
        base_query = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.full_play)
            .options(
                selectinload(PlaybackHistory.track),
                selectinload(PlaybackHistory.album).selectinload(Album.artists),
                selectinload(PlaybackHistory.device),
            )
        )

        # Count total
        count_query = base_query.with_only_columns(func.count()).order_by(None)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination with DESC order (newest first)
        paginated_query = (
            base_query
            .order_by(PlaybackHistory.played_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(paginated_query)
        plays = result.scalars().all()

        return PaginatedResponse[PlaybackHistorySimple](
            total=total,
            offset=offset,
            limit=limit,
            items=[PlaybackHistorySimple.model_validate(p) for p in plays],
        )

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
            .where(
                PlaybackHistory.user_uuid == user.user_uuid,
                PlaybackHistory.is_still_playing
            )
            .options(
                selectinload(PlaybackHistory.track),
                selectinload(PlaybackHistory.album).selectinload(Album.artists),
                selectinload(PlaybackHistory.device)
            )
            .order_by(PlaybackHistory.played_at.desc())
            .limit(1)
        )

        result = await self.db.exec(statement)
        playing = result.all()

        if playing:
            curr_playing = playing[0]
            played_at_utc = curr_playing.played_at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - played_at_utc).total_seconds() < 1000:
                return curr_playing
            else:
                return None
        else:
            return None

    async def get_current_play_message(self, user: User) -> dict:
        current_play: Optional[CurrentlyPlaying] = await self.get_currently_playing(user)
        return {
            "type": "current_play",
            "data": current_play.model_dump(mode="json") if current_play else None
        }

    async def add_listen(self, user: User, play: str):
        update = PlaybackUpdatePayload.model_validate(play)
        logger.info(f"Adding {update}")

        is_still_playing = update.state != "paused"

        current_playing = await self.get_currently_playing(user)

        if update.state == "paused" and not current_playing:
            logger.info(f"⏩ Skipping paused update — nothing currently playing.")
            return

        # Stage 1️⃣: Detect if same track without searching
        if current_playing and is_still_playing:
            if update.source == "Spotify" and update.track.spotify_track and current_playing.spotify_track_id == update.track.spotify_track:
                logger.info("🎵 Same Spotify track detected, updating currently playing only.")
                return

            if update.source == "Shazam" and update.track.song_name and current_playing.track.name:
                normalized_new = update.track.song_name.strip().lower()
                normalized_current = current_playing.track.name.strip().lower()
                if normalized_new == normalized_current:
                    logger.info("🎵 Same Shazam track title detected, updating currently playing only.")
                    return

        if update.source == "Shazam" and current_playing:
            if (
                    update.track.song_name and update.track.artist_name
                    and current_playing.track.name
                    and current_playing.album.artists
            ):
                normalized_current_name = current_playing.track.name.strip().lower()
                normalized_update_name = update.track.song_name.strip().lower()

                normalized_current_artist = current_playing.album.artists[0].name.strip().lower()
                normalized_update_artist = update.track.artist_name.strip().lower()

                if normalized_current_name == normalized_update_name and normalized_current_artist == normalized_update_artist:
                    logger.info(f"⏩ Skipping duplicate Shazam play for {update.track.song_name}")
                    return

        quick_update = CurrentlyPlaying(
            playback_history_uuid=uuid.uuid4(),
            spotify_track_id=update.track.spotify_track,
            played_at=datetime.now(timezone.utc).replace(tzinfo=None),
            source=update.source,
            full_play=True,
            full_update=False,
            is_still_playing=is_still_playing,
            track_uuid=uuid.uuid4(),
            album_uuid=uuid.uuid4(),
            track={
                "name": update.track.song_name,
                "track_uuid": uuid.uuid4()
            },
            album={
                "title": update.track.album_name,
                "album_uuid": uuid.uuid4(),
                "artists": [
                    ArtistBase(
                        artist_uuid=uuid.uuid4(),
                        name=update.track.artist_name
                    )
                ],
                "release_date": None
            }
        )

        await self.send_currently_playing(user, quick_update)


        # Stage 2️⃣: Search track
        read_tracks = await self.music_service.search_track(
            user_uuid=user.user_uuid,
            track_name=update.track.song_name,
            artist_name=update.track.artist_name,
            album_name=update.track.album_name,
            prefer_album_uuid=current_playing.album_uuid if current_playing else None,
        )

        device = await self.device_service.get_or_create_device(
            user=user,
            device_id=update.device.device_id,
            device_name=update.device.device_name
        )

        if read_tracks and device:
            read_track = read_tracks[0]

            if current_playing:
                median_duration = await self.get_median_duration(current_playing.track_uuid)
                played_at_utc = current_playing.played_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                time_elapsed = (now - played_at_utc).total_seconds()

                logger.info(f"Time elapsed: {time_elapsed} seconds of a median duration of {median_duration} seconds")

                if median_duration is not None and time_elapsed < (median_duration * 0.2):
                    current_playing.full_play = False
                else:
                    current_playing.full_play = True
                current_playing.is_still_playing = False
                self.db.add(current_playing)
                await self.db.flush()

            new_play = PlaybackHistory(
                spotify_track_id=update.track.spotify_track,
                user_uuid=user.user_uuid,
                track_uuid=read_track.track_uuid,
                album_uuid=read_track.albums[0].album_uuid if read_track.albums else None,
                source=update.source,
                device_uuid=device.device_uuid,
                full_play=True,
                is_still_playing=is_still_playing,
            )
            self.db.add(new_play)
            await self.db.commit()

            current_playing = await self.get_currently_playing(user)
            if current_playing:
                curr_playing = CurrentlyPlaying.model_validate(current_playing)
                curr_playing.is_still_playing = True
                curr_playing.full_update = True
                await self.send_currently_playing(user, curr_playing)
        else:
            if current_playing:
                median_duration = await self.get_median_duration(current_playing.track_uuid)
                played_at_utc = current_playing.played_at.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                time_elapsed = (now - played_at_utc).total_seconds()

                logger.info(f"Time elapsed: {time_elapsed} seconds of a median duration of {median_duration} seconds")

                if median_duration is not None and time_elapsed < (median_duration * 0.2):
                    current_playing.full_play = False
                else:
                    current_playing.full_play = True
                current_playing.is_still_playing = False
                self.db.add(current_playing)
                await self.db.flush()

            logger.debug(f"Skipping {update}, unknown song")

    # --- helper:
    async def get_median_duration(self, track_uuid: uuid.UUID) -> int:
        """
           Estimate median duration for a given track_uuid
           based on known TrackVersions.

           Returns seconds (float) or None if no data available.
           """
        query = (
            select(TrackVersion.duration)
            .where(TrackVersion.track_uuid == track_uuid)
            .where(TrackVersion.duration.is_not(None))
            .where(TrackVersion.duration > 0)
        )
        result = await self.db.execute(query)
        durations = [row[0] / 1000.0 for row in result.fetchall()]  # convert ms → s

        if not durations:
            return None

        durations.sort()
        n = len(durations)
        if n % 2 == 1:
            median = durations[n // 2]
        else:
            median = (durations[(n - 1) // 2] + durations[n // 2]) / 2.0
        return median

    def pick_best_albums(self, track, album_name: str) -> Optional[Album]:
        if not track.albums:
            return None

        # 1. Try to match by album name
        for album in track.albums:
            if album_name.lower() in album.title.lower():
                return album

        # 2. Fallback: pick earliest by release_date (or default to 9999 if missing)
        return sorted(
            track.albums,
            key=lambda a: a.release_date or datetime(9999, 1, 1)
        )[0]

    async def send_currently_playing(self, user: User, playing: CurrentlyPlaying):
        message_model = CurrentlyPlaying.model_validate(playing)
        await self.websocket_service.send_to_user(user.user_uuid, message_model)



