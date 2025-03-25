from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime, timedelta
from fastapi import HTTPException
from models.sqlmodels import SpotifyToken, PlaybackHistory
from config import settings
from services.connection_manager import manager
from models.appmodels import CurrentlyPlaying
import logging
from typing import Optional
import json
logger = logging.getLogger(__name__)


class SpotifyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.oauth = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope="user-read-playback-state user-read-currently-playing user-read-recently-played",
                show_dialog=False,
            )
        return cls._instance

    async def add_token_for_user(self, token: str, user_uuid: str, db: AsyncSession):
        token_info = self.oauth.get_access_token(token)
        expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

        result = await db.exec(select(SpotifyToken).where(SpotifyToken.user_uuid == user_uuid))
        existing = result.first()

        if existing:
            existing.access_token = token_info["access_token"]
            existing.refresh_token = token_info["refresh_token"]
            existing.expires_at = expires_at
        else:
            new_token = SpotifyToken(
                user_uuid=user_uuid,
                access_token=token_info["access_token"],
                refresh_token=token_info["refresh_token"],
                expires_at=expires_at,
            )
            db.add(new_token)

        await db.commit()
        return {"message": "Spotify authorized"}

    def get_redirect_url(self):
        return self.oauth.get_authorize_url()

    async def get_token_for_user(self, user_uuid: str, db: AsyncSession) -> str:
        result = await db.exec(select(SpotifyToken).where(SpotifyToken.user_uuid == user_uuid))
        token = result.first()

        if not token:
            raise HTTPException(status_code=404, detail="Spotify token not found for user.")

        if token.expires_at <= datetime.utcnow() + timedelta(minutes=5):
            logger.info(f"🔄 Refreshing token for user {user_uuid}")
            token_info = self.oauth.refresh_access_token(token.refresh_token)
            token.access_token = token_info["access_token"]
            token.expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

            if "refresh_token" in token_info:
                token.refresh_token = token_info["refresh_token"]

            db.add(token)
            await db.commit()

        return token.access_token

    def get_client(self, token: str) -> Spotify:
        return Spotify(auth=token)

    async def get_current_playback(self, user_uuid: str, db: AsyncSession):
        token = await self.get_token_for_user(user_uuid, db)
        sp_client = self.get_client(token)

        try:
            playback = sp_client.current_playback()
            return playback or {"status": "No active playback"}
        except Exception as e:
            logger.error(f"🔻 Spotify API error: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch playback info")

    def should_scrobble(self, track: dict) -> bool:
        return track.get("progress_ms", 0) >= 30_000

    async def get_currently_playing_state(self, user_uuid: str, db: AsyncSession) -> Optional[CurrentlyPlaying]:
        result = await db.exec(
            select(PlaybackHistory)
            .where(
                PlaybackHistory.user_uuid == user_uuid,
                PlaybackHistory.is_still_playing == True
            )
            .order_by(PlaybackHistory.played_at.desc())
        )
        latest = result.first()

        if latest:
            return CurrentlyPlaying(
                spotify_track_id=latest.spotify_track_id,
                track_name=latest.track_name,
                artist_name=latest.artist_name,
                album_name=latest.album_name,
                discogs_release_id=latest.discogs_release_id,
                played_at=latest.played_at,
                source=latest.source,
                device_name=latest.device_name,
                progress_ms=latest.progress_ms,
                duration_ms=latest.duration_ms,
                full_play=latest.full_play,
                is_still_playing=latest.is_still_playing
            )
        return None

    async def track_already_scrobbled(self, db: AsyncSession, user_uuid: str, track_id: str, played_at: datetime) -> bool:
        result = await db.exec(
            select(PlaybackHistory).where(
                PlaybackHistory.user_uuid == user_uuid,
                PlaybackHistory.spotify_track_id == track_id,
                PlaybackHistory.played_at == played_at,
            )
        )
        return result.first() is not None

    async def gather_user_playback_history(self, user_uuid: str, db: AsyncSession, limit: int = 50):
        playback = await self.get_current_playback(user_uuid, db)
        if not isinstance(playback, dict) or "item" not in playback:
            return

        try:
            track_info = playback["item"]
            progress_ms = playback.get("progress_ms", 0)
            artist = track_info["artists"][0]
            album = track_info["album"]
            track_name = track_info["name"]
            track_id = track_info["id"]
            album_name = album["name"]
            artist_name = artist["name"]
            device_name = playback.get("device", {}).get("name", "unknown")
            duration_ms = track_info.get("duration_ms")
            still_playing = playback.get("is_playing", False)
            timestamp = playback.get("timestamp", int(datetime.utcnow().timestamp() * 1000))
            played_at = datetime.utcfromtimestamp(timestamp / 1000.0)

            logger.info(
                f"🎧 Polling: {track_name} by {artist_name} for user {user_uuid} - progress {progress_ms}ms"
            )

            current_state = await self.get_currently_playing_state(user_uuid, db)

            if current_state and current_state.spotify_track_id == track_id:
                logger.debug(f"🔁 Updating current session for {track_name}")
                result = await db.exec(
                    select(PlaybackHistory)
                    .where(
                        PlaybackHistory.user_uuid == user_uuid,
                        PlaybackHistory.spotify_track_id == track_id,
                        PlaybackHistory.is_still_playing == True
                    )
                    .order_by(PlaybackHistory.played_at.desc())
                )
                current_session = result.first()
                if current_session:
                    current_session.progress_ms = progress_ms
                    current_session.is_still_playing = still_playing
                    db.add(current_session)

            else:
                logger.info(f"▶️ New track for user {user_uuid}: {track_name}")

                if current_state:
                    result = await db.exec(
                        select(PlaybackHistory)
                        .where(
                            PlaybackHistory.user_uuid == user_uuid,
                            PlaybackHistory.spotify_track_id == current_state.spotify_track_id,
                            PlaybackHistory.is_still_playing == True
                        )
                    )
                    old_session = result.first()
                    if old_session:
                        old_session.is_still_playing = False
                        db.add(old_session)

                scrobble = PlaybackHistory(
                    user_uuid=user_uuid,
                    spotify_track_id=track_id,
                    track_name=track_name,
                    artist_name=artist_name,
                    album_name=album_name,
                    played_at=played_at,
                    source="spotify",
                    device_name=device_name,
                    duration_ms=duration_ms,
                    progress_ms=progress_ms,
                    full_play=False,  # Always false for now
                    is_still_playing=still_playing
                )
                db.add(scrobble)

            await db.commit()

            if manager.has_connections(user_uuid):
                now_playing = CurrentlyPlaying(
                    spotify_track_id=track_id,
                    track_name=track_name,
                    artist_name=artist_name,
                    album_name=album_name,
                    played_at=played_at,
                    source="spotify",
                    device_name=device_name,
                    duration_ms=duration_ms,
                    progress_ms=progress_ms,
                    is_still_playing=still_playing,
                    full_play=False,
                    discogs_release_id=None,
                )
                await manager.send_to_user(user_uuid, {
                    "type": "current_play",
                    "data": now_playing.model_dump(mode="json")
                })

            logger.info(f"✅ Tracked: {track_name} by {artist_name} for user {user_uuid}")

        except Exception as e:
            logger.warning(f"⚠️ Error polling user {user_uuid}: {e}")


