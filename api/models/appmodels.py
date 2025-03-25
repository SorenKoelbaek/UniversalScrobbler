from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_serializer
from datetime import datetime, timezone


class PlaybackHistoryBase(BaseModel):
    spotify_track_id: Optional[str]
    track_name: str
    artist_name: str
    album_name: str
    discogs_release_id: Optional[int]
    played_at: datetime
    source: str = "spotify"
    device_name: Optional[str] = None
    progress_ms: Optional[int]
    duration_ms: Optional[int]
    full_play: Optional[bool] = False

class CurrentlyPlaying(PlaybackHistoryBase):
    is_still_playing: bool

class PlaybackHistoryRead(PlaybackHistoryBase):
    playback_history_uuid: UUID

class SpotifyTokenRead(BaseModel):
    spotify_token_uuid: UUID
    access_token: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_expires_at(self, dt: datetime, _info) -> str:
        return dt.replace(tzinfo=timezone.utc).isoformat()

class UserBase(BaseModel):
    """Base model for a user."""
    username: str
    email: str
    status: Optional[str] = None


class UserRead(UserBase):
    """Model for reading user details."""
    user_uuid: UUID
    spotify_token: Optional[SpotifyTokenRead]


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class SpotifyAuthRequest(BaseModel):
    code: str

