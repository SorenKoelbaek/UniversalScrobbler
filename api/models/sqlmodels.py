from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import func
from datetime import datetime
from typing import Optional, List

from uuid import UUID, uuid4
from datetime import datetime

class User(SQLModel, table=True):
    """SQL representation of a user."""
    __tablename__ = "appuser"

    user_uuid: UUID = Field(
        primary_key=True,
        default_factory=uuid4,
        sa_column_kwargs={"unique": True, "server_default": func.gen_random_uuid()},
    )
    username: str
    status: str
    email: str
    created_at: datetime = Field(sa_column_kwargs={"server_default": func.now()})
    password: str
    spotify_token: Optional["SpotifyToken"] = Relationship(back_populates="user")
    playback_history: List["PlaybackHistory"] = Relationship(back_populates="user")


class SpotifyToken(SQLModel, table=True):
    """Spotify token info linked to a user."""
    spotify_token_uuid: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"unique": True, "server_default": func.gen_random_uuid()},
    )
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid", nullable=False, unique=True)
    access_token: str
    refresh_token: str
    expires_at: datetime
    user: Optional["User"] = Relationship(back_populates="spotify_token")
    scope: Optional[str] = None

class PlaybackHistory(SQLModel, table=True):
    __tablename__ = "playback_history"

    playback_history_uuid: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"unique": True, "server_default": func.gen_random_uuid()},
    )

    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")
    spotify_track_id: Optional[str]  # Spotify track ID
    track_name: str
    artist_name: str
    album_name: str
    discogs_release_id: Optional[int]
    played_at: datetime
    source: str = "spotify"  # Optional discriminator later
    device_name: Optional[str] = None  # optional: add device_id if needed

    user: Optional["User"] = Relationship(back_populates="playback_history")
