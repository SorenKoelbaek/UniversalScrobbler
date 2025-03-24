import uuid

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from sqlmodel import Session, select
from datetime import datetime, timedelta
from models.sqlmodels import SpotifyToken, PlaybackHistory
from config import settings
from fastapi import HTTPException

import logging
from collections import Counter

logger = logging.getLogger(__name__)

class SpotifyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpotifyService, cls).__new__(cls)
            cls._instance.oauth = SpotifyOAuth(
                client_id=settings.SPOTIFY_CLIENT_ID,
                client_secret=settings.SPOTIFY_CLIENT_SECRET,
                redirect_uri=settings.SPOTIFY_REDIRECT_URI,
                scope="user-read-playback-state user-read-currently-playing user-read-recently-played",
                show_dialog=False,
            )
        return cls._instance

    def add_token_for_user(self, token: str, user_uuid: str, db: Session):

        token_info = self.oauth.get_access_token(token)

        expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

        existing = db.exec(select(SpotifyToken).where(SpotifyToken.user_uuid == user_uuid)).first()

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

        db.commit()
        return {"message": "Spotify authorized"}

    def get_redirect_url(self):
        """
        Generate the Spotify authorization URL.
        """
        return self.oauth.get_authorize_url()

    def get_token_for_user(self, user_uuid: str, db: Session) -> str:
        """
        Fetch the valid Spotify access token for a user, refreshing it if expired.
        """
        token = db.exec(
            select(SpotifyToken).where(SpotifyToken.user_uuid == user_uuid)
        ).first()

        if not token:
            raise HTTPException(status_code=404, detail="Spotify token not found for user.")

        # Refresh the token if it's expired
        if token.expires_at <= datetime.utcnow() + timedelta(minutes=5):
            logger.info(f"🔄 Refreshing token for user {user_uuid}")
            token_info = self.oauth.refresh_access_token(token.refresh_token)

            token.access_token = token_info["access_token"]
            token.expires_at = datetime.utcnow() + timedelta(seconds=token_info["expires_in"])

            if "refresh_token" in token_info:
                token.refresh_token = token_info["refresh_token"]

            db.add(token)
            db.commit()

        return token.access_token

    def get_client(self, token: str) -> Spotify:
        """Returns a Spotify client with the given access token"""
        return Spotify(auth=token)

    def get_current_playback(self, user_uuid: str, db: Session):
        """
        Get the current playback information for a user.
        """
        token = self.get_token_for_user(user_uuid, db)
        sp_client = self.get_client(token)

        try:
            playback = sp_client.current_playback()

            if not playback:
                return {"status": "No active playback"}

            return {
                "is_playing": playback["is_playing"],
                "item": {
                    "name": playback["item"]["name"],
                    "artists": [a["name"] for a in playback["item"]["artists"]],
                    "album": playback["item"]["album"]["name"],
                },
                "device": playback["device"]["name"],
            }

        except Exception as e:
            logger.error(f"🔻 Spotify API error: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch playback info")

    def should_scrobble(self, track):
        """
        Determines if the track meets the criteria to be scrobbled.
        This can be adjusted later based on new scrobble criteria.
        """
        min_played_time = 30  # Minimum time (in seconds) before scrobbling
        if track.get("progress_ms", 0) >= min_played_time * 1000:  # progress_ms is in milliseconds
            return True
        return False

    def track_already_scrobbled(self, session: Session, user_uuid: str, track_id: str, played_at: datetime) -> bool:
        """
        Check if a track has already been scrobbled by the user.
        This prevents duplicate entries in the playback history.
        """
        existing = session.exec(
            select(PlaybackHistory).where(
                PlaybackHistory.user_uuid == user_uuid,
                PlaybackHistory.spotify_track_id == track_id,
                PlaybackHistory.played_at == played_at,
            )
        ).first()

        return existing is not None

    def gather_user_playback_history(self, user_uuid: str, db: Session, limit: int = 50):
        """
        Gather recent playback history for a user, using recursive fetch from last known playback.
        """
        token = self.get_token_for_user(user_uuid, db)
        sp_client = self.get_client(token)

        from datetime import timezone

        # Get most recent scrobble for this user
        latest_play = db.exec(
            select(PlaybackHistory.played_at)
            .where(PlaybackHistory.user_uuid == user_uuid)
            .order_by(PlaybackHistory.played_at.desc())
        ).first()

        after = None
        if latest_play:
            after_dt = latest_play.replace(tzinfo=timezone.utc)
            after = int(after_dt.timestamp() * 1000)  # milliseconds

        total_added = 0

        try:
            while True:
                params = {"limit": limit}
                if after:
                    params["after"] = after

                recently_played = sp_client._get("me/player/recently-played", **params)

                items = recently_played.get("items", [])
                if not items:
                    break

                added_this_round = 0
                for item in items:
                    track = item["track"]
                    played_at = datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))

                    if self.track_already_scrobbled(db, user_uuid, track["id"], played_at):
                        continue

                    if track["duration_ms"] < 30_000:
                        continue

                    playback_history = PlaybackHistory(
                        user_uuid=user_uuid,
                        track_name=track["name"],
                        artist_name=track["artists"][0]["name"],
                        album_name=track["album"]["name"],
                        spotify_track_id=track["id"],
                        played_at=played_at,
                        source="spotify",
                        device_name=None,
                        discogs_release_id=None,
                    )

                    db.add(playback_history)
                    logger.info(f"✅ Scrobbled: {track['name']} by {track['artists'][0]['name']}")
                    added_this_round += 1
                    total_added += 1

                db.commit()

                if len(items) < limit or added_this_round == 0:
                    break  # no more to fetch or no new additions

                # Continue with next batch after last played_at
                after = int(items[-1]["played_at"].replace("Z", "+00:00").timestamp() * 1000)

        except Exception as e:
            logger.error(f"Error gathering playback history for user {user_uuid}: {e}")
            raise HTTPException(status_code=500, detail="Failed to gather playback history")

