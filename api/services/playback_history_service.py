import uuid
from mimetypes import knownfiles
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from typing import List, Optional
from collections import Counter
from models.sqlmodels import PlaybackHistory, User, Track, Album
from models.appmodels import PlaybackHistorySimple, CurrentlyPlaying, PlaybackUpdatePayload, ArtistBase, AlbumBase
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

    async def get_user_playback_history(self, user: User, days: int = 7) -> List[PlaybackHistorySimple]:
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

        statement = (
            select(PlaybackHistory)
            .where(PlaybackHistory.user_uuid == user.user_uuid)
            .where(PlaybackHistory.played_at >= since)
            .where(PlaybackHistory.full_play)
            .options(selectinload(PlaybackHistory.track),
                     selectinload(PlaybackHistory.album).selectinload(Album.artists),
                     selectinload(PlaybackHistory.device))
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
            .where(PlaybackHistory.user_uuid == user.user_uuid, PlaybackHistory.is_still_playing)
            .options(selectinload(PlaybackHistory.track),
                     selectinload(PlaybackHistory.album).selectinload(Album.artists),
                     selectinload(PlaybackHistory.device))
            .order_by(PlaybackHistory.played_at.desc())
            .limit(1)
        )

        result = await self.db.exec(statement)
        playing = result.all()
        if len(playing)> 0:
            curr_playing = playing[0]

            played_at_utc = curr_playing.played_at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - played_at_utc).total_seconds() < 1000:
                return curr_playing
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
        logger.debug(f"Adding {update}")

        quick_update = CurrentlyPlaying(
            playback_history_uuid=uuid.uuid4(),
            spotify_track_id=update.track.spotify_track,
            played_at=datetime.now(timezone.utc).replace(tzinfo=None),
            source=update.source,
            full_play=False,
            full_update=False,
            is_still_playing=True,
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

        # trying to resolve into objects we know
        read_tracks = await self.music_service.search_track(
            user_uuid=user.user_uuid,
            track_name=update.track.song_name,
            artist_name=update.track.artist_name,
            album_name=update.track.album_name)

        device = await self.device_service.get_or_create_device(
            user=user,
            device_id=update.device.device_id,
            device_name=update.device.device_name)
        if read_tracks and device:

            read_track = read_tracks[0]
            logger.info(f"📜 Read track: {read_track.track_uuid} full: {read_track}")
            for obj in self.db.identity_map.values():
                logger.warning(f"PENDING: {obj.__class__.__name__} -> {obj}")
            current_playing = await self.get_currently_playing(user)


            if update.state == "paused" or update.state == "stopped":
                if current_playing:
                    current_playing.full_play = False
                    self.db.add(current_playing)
                    await self.db.commit()
                    curr_playing = CurrentlyPlaying.model_validate(current_playing)
                    curr_playing.is_still_playing = False
                    curr_playing.full_update = True
                    await self.send_currently_playing(user, curr_playing)

            if update.state == "playing":
                if current_playing:
                    played_at_utc = current_playing.played_at.replace(tzinfo=timezone.utc)

                    if current_playing.track_uuid == read_track.track_uuid:
                        if (update.timestamp - played_at_utc).total_seconds() < 1000: # TODO: add a way to determine this based on track duration?
                            return # maybe add device update here?
                        else:
                            current_playing.full_play = True
                            current_playing.is_still_playing = False
                    else:
                        if (update.timestamp - played_at_utc).total_seconds() < 30: # TODO: add a way to determine this based on track duration?
                            current_playing.full_play = False
                        else:
                            current_playing.full_play = True
                        current_playing.is_still_playing = False

                    self.db.add(current_playing)
                    await self.db.flush()


                new_play = PlaybackHistory(
                    spotify_track_id=update.track.spotify_track,
                    user_uuid = user.user_uuid,
                    track_uuid = read_track.track_uuid,
                    album_uuid =  self.pick_best_albums(read_track,update.track.album_name).album_uuid,
                    source = update.source,
                    device_uuid = device.device_uuid,
                    full_play = False,
                    is_still_playing = True
                )
                self.db.add(new_play)
                await self.db.commit()

                current_playing = await self.get_currently_playing(user)
                curr_playing = CurrentlyPlaying.model_validate(current_playing)
                curr_playing.is_still_playing = True
                curr_playing.full_update = True
                await self.send_currently_playing(user, curr_playing)
        else:
            logger.debug(f"Skipping {update}, unknown song")

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



