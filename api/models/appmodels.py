from typing import Optional, Union
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_serializer, field_validator, model_validator, Field, AliasPath, computed_field
from datetime import datetime, timezone
from typing import Generic, TypeVar, List

T = TypeVar("T")
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
    title: str = Field(..., alias=AliasPath("album", "title"))
    artists: List["ArtistBase"] = Field(..., alias=AliasPath("album", "artists"))
    release_date: Optional[datetime] = Field(..., alias=AliasPath("album", "release_date"))
    full_update: Optional[bool] = False

    class Config:
        from_attributes=True

class CurrentlyPlaying(PlaybackHistorySimple):
    duration_seconds: Optional[int] = None
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
    track_number: Optional[str] = None

    class Config:
        from_attributes=True


class ArtistBase(BaseModel):
    artist_uuid: UUID
    name: str


    class Config:
        from_attributes=True

class AlbumTypeBase(BaseModel):
    album_type_uuid: UUID
    name: str

    class Config:
        from_attributes=True

class AlbumTypeRead(AlbumTypeBase):
    description: Optional[str] = None

    class Config:
        from_attributes=True

class AlbumBase(BaseModel):
    image_url: Optional[str] = None
    image_thumbnail_url: Optional[str] = None
    album_uuid: UUID
    title: str
    discogs_master_id: Optional[int] = None  # Master ID for the album
    release_date: Optional[datetime] = None
    types: List[AlbumTypeBase] = []  # List of types (e.g., LP, EP, etc.)

    class Config:
        from_attributes=True

class AlbumSimpleRead(AlbumBase):
    artists: List[ArtistBase]  # List of artists associated with this master album


# New Model to represent Album Releases (specific versions of an album)
class AlbumReleaseBase(BaseModel):
    album_release_uuid: UUID
    title: str
    discogs_release_id: Optional[int] = None
    release_date: Optional[datetime] = None  # The release date for this specific version
    country: Optional[str] = None  # The country of release
    is_main_release: bool = False  # Is this the main release for the album (usually for master album)

    class Config:
        from_attributes=True

class TrackVersionBase(BaseModel):
    track_version_uuid: UUID
    album_releases: Optional[List[AlbumReleaseBase]] = []  # The album release this version belongs to
    duration: Optional[int] = None  # Duration of the track in seconds
    recording_id: str
    tags: List["TagBase"] = []  # List of tags associated with this track version

    class Config:
        from_attributes=True

class TrackReadSimple(TrackBase):
    albums: List[AlbumBase]
    artists: List[ArtistBase]

    class Config:
        from_attributes=True

class TrackRead(TrackReadSimple):
    track_versions: List[TrackVersionBase]
    class Config:
        from_attributes=True

# Artist with albums they are associated with
class ArtistRead(ArtistBase):
    discogs_artist_id: Optional[int]
    name_variations: Optional[str] = None
    profile: Optional[str] = None
    albums: Optional[List[AlbumBase]] = []  # List of albums (master) the artist is featured on
    album_releases: Optional[List[AlbumReleaseBase]] = []  # List of album releases the artist is featured on
    tags: List["TagBase"] = []
    class Config:
        from_attributes=True

class AlbumSimple(AlbumBase):
    artists: List[ArtistBase]  # List of artists associated with this master album

    class Config:
        from_attributes=True

class TagBase(BaseModel):
    tag_uuid: UUID
    name: str
    count: Optional[int] = 0

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

class CollectionAlbumFormatRead(BaseModel):
    format: str
    status: str

    class Config:
        from_attributes = True

class AlbumFlat(BaseModel):
    album_uuid: UUID
    title: str = Field(alias="title")
    release_date: Optional[datetime]
    image_url: Optional[str]
    image_thumbnail_url: Optional[str]
    artists: List[ArtistBase]
    releases: List[AlbumReleaseBase] = []
    formats: List[CollectionAlbumFormatRead] = Field(
        default_factory=list,
        alias=AliasPath("collectionalbumbridge", 0, "formats")  # 🔑 reach through bridge
    )


    class Config:
        from_attributes = True
        populate_by_name = True

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



class AlbumInCollection(AlbumSimple):
    formats: List[CollectionAlbumFormatRead] = []

    class Config:
        from_attributes = True

class CollectionBase(BaseModel):
    collection_uuid: UUID
    collection_name: str

    class Config:
        from_attributes=True

class CollectionTrackBase(BaseModel):
    collection_track_uuid: UUID
    collection_uuid: UUID
    track_version_uuid: UUID
    path: Optional[str] = None
    quality: Optional[str] = None
    format: Optional[str] = None
    added_at: datetime

    class Config:
        from_attributes = True

class CollectionTrackRead(CollectionTrackBase):
    track_version: Optional[TrackVersionBase] = None

    class Config:
        from_attributes = True

class CollectionSimple(CollectionBase):
    albums: List[AlbumBase]
    album_releases: List[AlbumReleaseSimple]

    class Config:
        from_attributes=True

class CollectionSimpleRead(CollectionBase):
    albums: list[AlbumFlat]
    tracks: List[CollectionTrackRead]

    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    offset: int
    limit: int
    items: List[T]

# CollectionRead represents a user's collection and all albums/releases in it
class CollectionRead(CollectionBase):
    albums: List[AlbumInCollection]  # List of albums (master) in the collection
    album_releases: List[AlbumReleaseBase]  # List of album releases in the collection
    created_at: Optional[datetime]  # Track when collection was created
    tracks: List[CollectionTrackRead]

    class Config:
        from_attributes=True

class MusicSearchResponse(BaseModel):
    type: str
    result: Union[List[TrackReadSimple],List[AlbumRead],List[ArtistRead]]


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


class websocketMessage(BaseModel):
    type: Optional[str]
    payload: Optional[dict]

class AlbumFindSimilarRequest(BaseModel):
    albums: List[UUID]
    years: Optional[List[int]] = None
    artists: Optional[List[UUID]] = None
    styles: Optional[List[UUID]] = None
    types: Optional[List[UUID]] = None

class ListenArtist(BaseModel):
    name: str
    mbid: Optional[str]

class ListenAlbum(BaseModel):
    name: str
    mbid: Optional[str]

class ListenTrack(BaseModel):
    name: str
    duration_ms: Optional[int]
    mbid: Optional[str]
    uri: Optional[str]

class ListenEvent(BaseModel):
    source: str
    played_at: datetime
    reported_at: datetime
    track: ListenTrack
    album: ListenAlbum
    artists: List[ListenArtist]