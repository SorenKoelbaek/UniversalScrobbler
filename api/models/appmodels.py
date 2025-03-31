from typing import Optional, List, Union
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_serializer
from datetime import datetime, timezone
from pydantic.alias_generators import to_camel

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

class DiscogsTokenRead(BaseModel):
    discogs_token_uuid: UUID
    access_token: str

class UserBase(BaseModel):
    """Base model for a user."""
    username: str
    email: str
    status: Optional[str] = None


class UserRead(UserBase):
    """Model for reading user details."""
    user_uuid: UUID
    spotify_token: Optional[SpotifyTokenRead]
    discogs_token: Optional[DiscogsTokenRead]

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class SpotifyAuthRequest(BaseModel):
    code: str

class DiscogsAuthRequest(BaseModel):
    oauth_token: str
    oauth_verifier: str


# Base Models for database entities
class TrackBase(BaseModel):
    track_uuid: UUID
    name: str

    class Config:
        from_attributes=True


class ArtistBase(BaseModel):
    artist_uuid: UUID
    name: str


    class Config:
        from_attributes=True

class AlbumBase(BaseModel):
    album_uuid: UUID
    title: str
    styles: Optional[str] = None
    country: Optional[str] = None
    discogs_master_id: Optional[int] = None  # Master ID for the album
    release_date: Optional[datetime] = None

    class Config:
        from_attributes=True

class AlbumSimpleRead(AlbumBase):
    artists: List[ArtistBase]  # List of artists associated with this master album


# New Model to represent Album Releases (specific versions of an album)
class AlbumReleaseBase(BaseModel):
    album_release_uuid: UUID
    discogs_release_id: int
    release_date: Optional[datetime] = None  # The release date for this specific version
    country: Optional[str] = None  # The country of release
    is_main_release: bool = False  # Is this the main release for the album (usually for master album)

    class Config:
        from_attributes=True

class TrackRead(TrackBase):
    albums: List[AlbumSimpleRead]  # The album (master) this track belongs to

    class Config:
        from_attributes=True

# Artist with albums they are associated with
class ArtistRead(ArtistBase):
    discogs_artist_id: Optional[int]
    name_variations: Optional[str] = None
    profile: Optional[str] = None
    albums: Optional[List[AlbumBase]] = []  # List of albums (master) the artist is featured on
    album_releases: Optional[List[AlbumReleaseBase]] = []  # List of album releases the artist is featured on

    class Config:
        from_attributes=True


# AlbumRead reflects the "master album" which may have many releases
class AlbumRead(AlbumBase):
    artists: List[ArtistBase]  # List of artists associated with this master album
    tracks: List[TrackBase]  # List of tracks for this master album (not specific to any release)

    class Config:
        from_attributes=True


# AlbumReleaseRead reflects a specific release of an album
class AlbumReleaseRead(AlbumReleaseBase):
    album: AlbumBase  # The master album for this release
    artists: List[ArtistBase]  # Artists for this specific release
    tracks: List[TrackBase]  # Tracks for this specific release

    class Config:
        from_attributes=True

class CollectionBase(BaseModel):
    collection_uuid: UUID
    collection_name: str

    class Config:
        from_attributes=True

class AlbumReleaseSimple(BaseModel):
    album_release_uuid: UUID
    discogs_release_id: Optional[int]

    class Config:
        from_attributes=True

class CollectionSimple(CollectionBase):
    album_releases: list[AlbumReleaseSimple]

    class Config:
        from_attributes=True


# CollectionRead represents a user's collection and all albums/releases in it
class CollectionRead(CollectionBase):
    albums: List[AlbumRead]  # List of albums (master) in the collection
    album_releases: List[AlbumReleaseBase]  # List of album releases in the collection
    created_at: Optional[datetime]  # Track when collection was created

    class Config:
        from_attributes=True

class MusicSearchResponse(BaseModel):
    type: str
    result: Union[List[TrackRead],List[AlbumRead],List[ArtistRead]]