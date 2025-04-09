from typing import Optional, List, Union
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_serializer, field_validator, model_validator, Field, AliasPath
from datetime import datetime, timezone

class DeviceBase(BaseModel):
    device_uuid: UUID
    device_name: str
    location: Optional[str] = None
    context : Optional[str] = None

class PlaybackHistoryBase(BaseModel):
    playback_history_uuid:UUID
    spotify_track_id: Optional[str]
    played_at: datetime
    source: Optional[str]
    full_play: Optional[bool] = False

    class Config:
        from_attributes=True

class PlaybackHistoryRead(PlaybackHistoryBase):
    track: "TrackBase"
    album: "AlbumSimple"
    device: DeviceBase

    class Config:
        from_attributes=True


class PlaybackHistorySimple(PlaybackHistoryBase):
    track_uuid: UUID
    album_uuid: UUID
    song_title:str = Field(..., alias=AliasPath("track", "name"))
    album_title: str = Field(..., alias=AliasPath("album", "title"))
    artists: List["ArtistBase"] = Field(..., alias=AliasPath("album", "artists"))
    release_date: Optional[datetime] = Field(..., alias=AliasPath("album", "release_date"))
    full_update: Optional[bool] = False

    class Config:
        from_attributes=True

class CurrentlyPlaying(PlaybackHistorySimple):
    is_still_playing: bool


    class Config:
        from_attributes=True

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
    image_url: Optional[str] = None
    image_thumbnail_url: Optional[str] = None
    album_uuid: UUID
    title: str
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
    albums: List[AlbumBase]
    artists: List[ArtistBase]
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

class AlbumSimple(AlbumBase):
    artists: List[ArtistBase]  # List of artists associated with this master album

    class Config:
        from_attributes=True

class TagBase(BaseModel):
    tag_uuid: UUID
    name: str
    count: Optional[int] = 0  # Number of times this tag is used

    class Config:
        from_attributes=True

class GenreBase(BaseModel):
    genre_uuid: UUID
    name: str

    class Config:
        from_attributes=True


# AlbumRead reflects the "master album" which may have many releases
class AlbumRead(AlbumBase):
    releases: List[AlbumReleaseBase]  # List of releases for this master album
    artists: List[ArtistBase]  # List of artists associated with this master album
    tracks: List[TrackBase]  # List of tracks for this master album (not specific to any release)
    tags: List[TagBase] = []  # List of genres associated with this album

    class Config:
        from_attributes=True

class AlbumReleaseFlat(BaseModel):
    album_release_uuid: UUID
    album_title: str = Field(..., alias=AliasPath("album", "title"))
    album_uuid: UUID = Field(..., alias=AliasPath("album", "album_uuid"))
    release_date: Optional[datetime] = Field(..., alias=AliasPath("album", "release_date"))
    image_url: Optional[str] = Field(..., alias=AliasPath("album", "image_url"))
    image_thumbnail_url: Optional[str] = Field(..., alias=AliasPath("album", "image_thumbnail_url"))
    class Config:
        from_attributes=True
    artists: List[ArtistBase] = Field(..., alias=AliasPath("album", "artists"))
    class Config:
        from_attributes = True

# AlbumReleaseRead reflects a specific release of an album
class AlbumReleaseRead(AlbumReleaseBase):
    album: AlbumBase  # The master album for this release
    artists: List[ArtistBase]  # Artists for this specific release
    tracks: List[TrackBase]  # Tracks for this specific release

    class Config:
        from_attributes=True

class AlbumReleaseSimple(BaseModel):
    album_release_uuid: UUID
    discogs_release_id: Optional[int]

    class Config:
        from_attributes=True


class CollectionBase(BaseModel):
    collection_uuid: UUID
    collection_name: str

    class Config:
        from_attributes=True


class CollectionSimple(CollectionBase):
    albums: List[AlbumBase]
    album_releases: List[AlbumReleaseSimple]

    class Config:
        from_attributes=True

class CollectionSimpleRead(CollectionBase):
    album_releases: list[AlbumReleaseFlat]

    class Config:
        from_attributes = True

# CollectionRead represents a user's collection and all albums/releases in it
class CollectionRead(CollectionBase):
    albums: List[AlbumSimple]  # List of albums (master) in the collection
    album_releases: List[AlbumReleaseBase]  # List of album releases in the collection
    created_at: Optional[datetime]  # Track when collection was created

    class Config:
        from_attributes=True

class MusicSearchResponse(BaseModel):
    type: str
    result: Union[List[TrackRead],List[AlbumRead],List[ArtistRead]]


class PlaybackUpdateTrack(BaseModel):
    song_name: Optional[str]
    artist_name: Optional[str]
    album_name: Optional[str]
    spotify_track: Optional[str]


class PlaybackUpdateDevice(BaseModel):
    device_id: Optional[str]
    device_name: Optional[str]


class PlaybackUpdatePayload(BaseModel):
    state: Optional[str]
    source: Optional[str]  # NEW: 'spotify' or 'shazam'
    track: Optional[PlaybackUpdateTrack]
    device: Optional[PlaybackUpdateDevice]
    timestamp: Optional[datetime] = datetime.now(timezone.utc)


class websocketMessage(BaseModel):
    type: Optional[str]
    payload: Optional[dict]