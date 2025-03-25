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
        if not isinstance(playback, dict):
            return

        try:
            track_info = playback["item"]
            progress_ms = playback.get("progress_ms", 0)
            played_at = datetime.utcnow() - timedelta(milliseconds=progress_ms)
            artist = track_info["artists"][0]
            album = track_info["album"]
            track_name = track_info["name"]
            track_id = track_info["id"]
            album_name = album["name"]
            artist_name = artist["name"]
            device_name = playback.get("device", {}).get("name", "unknown")
            duration_ms = track_info.get("duration_ms")
            still_playing = playback.get("is_playing", False)

            logger.info(
                f"🎧 should I scrobble {track_name} by {artist_name} for user {user_uuid} - been playing for {progress_ms}ms?"
            )

            full_play = self.should_scrobble(playback)

            tolerance = timedelta(seconds=10)
            lower_bound = played_at - tolerance
            upper_bound = played_at + tolerance

            result = await db.exec(
                select(PlaybackHistory).where(
                    PlaybackHistory.user_uuid == user_uuid,
                    PlaybackHistory.spotify_track_id == track_id,
                    PlaybackHistory.played_at.between(lower_bound, upper_bound)
                )
            )
            existing = result.first()

            if not existing:
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
                    full_play=full_play,
                    is_still_playing = still_playing
                )
                db.add(scrobble)
            else:
                existing.progress_ms = progress_ms
                existing.full_play = full_play
                db.add(existing)

            await db.commit()
            logger.info(manager)
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
                    full_play=full_play,
                    discogs_release_id=None,
                )

                await manager.send_to_user_async(user_uuid, {
                    "type": "current_play",
                    "data": now_playing.model_dump(mode="json")
                })

            logger.info(f"✅ Scrobbled: {track_name} by {artist_name} for user {user_uuid}")

        except Exception as e:
            logger.warning(f"⚠️ Error polling user {user_uuid}: {e}")
