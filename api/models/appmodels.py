from typing import Optional, Union, Generic, TypeVar, List
from uuid import UUID
from pydantic import (
    BaseModel,
    EmailStr,
    field_serializer,
    Field,
    AliasPath,
    root_validator,
)
from datetime import datetime, timezone

T = TypeVar("T")

# -------------------------------------------------------------------
# Device / Playback History
# -------------------------------------------------------------------

class DeviceSwitchRequest(BaseModel):
    device_uuid: UUID

class DeviceBase(BaseModel):
    device_uuid: UUID
    device_name: str
    location: Optional[str] = None
    context: Optional[str] = None


class PlaybackHistoryBase(BaseModel):
    playback_history_uuid: UUID
    played_at: datetime


    class Config:
        from_attributes = True


class PlaybackHistoryRead(PlaybackHistoryBase):
    track: "TrackBase"
    album: "AlbumSimple"
    device: DeviceBase

    class Config:
        from_attributes = True


class PlaybackHistorySimple(PlaybackHistoryBase):
    track_uuid: UUID
    album_uuid: UUID
    song_title: str = Field(..., alias=AliasPath("track", "name"))
    title: str = Field(..., alias=AliasPath("album", "title"))
    artists: List["ArtistBase"] = Field(..., alias=AliasPath("album", "artists"))
    release_date: Optional[datetime] = Field(
        ..., alias=AliasPath("album", "release_date")
    )
    full_update: Optional[bool] = False

    class Config:
        from_attributes = True


# -------------------------------------------------------------------
# Tokens
# -------------------------------------------------------------------

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


# -------------------------------------------------------------------
# User
# -------------------------------------------------------------------

class UserBase(BaseModel):
    username: str
    email: str
    status: Optional[str] = None


class UserRead(UserBase):
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


# -------------------------------------------------------------------
# Music Models
# -------------------------------------------------------------------

class TrackBase(BaseModel):
    track_uuid: UUID
    name: str
    track_number: Optional[str] = None
    library_track_uuid: UUID | None = None
    track_position: Optional[int] = None  # Normalized 1..N index
    has_digital: bool = False

    class Config:
        from_attributes = True


class ArtistBase(BaseModel):
    artist_uuid: UUID
    name: str

    class Config:
        from_attributes = True


class AlbumTypeBase(BaseModel):
    album_type_uuid: UUID
    name: str

    class Config:
        from_attributes = True


class AlbumTypeRead(AlbumTypeBase):
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AlbumBase(BaseModel):
    image_url: Optional[str] = None
    image_thumbnail_url: Optional[str] = None
    album_uuid: UUID
    title: str
    discogs_master_id: Optional[int] = None
    release_date: Optional[datetime] = None
    types: List[AlbumTypeBase] = []

    class Config:
        from_attributes = True


class AlbumSimpleRead(AlbumBase):
    artists: List[ArtistBase]


class AlbumReleaseBase(BaseModel):
    album_release_uuid: UUID
    title: str
    discogs_release_id: Optional[int] = None
    release_date: Optional[datetime] = None
    country: Optional[str] = None
    is_main_release: bool = False

    class Config:
        from_attributes = True


class TrackVersionBase(BaseModel):
    track_version_uuid: UUID
    album_releases: Optional[List[AlbumReleaseBase]] = []
    duration: Optional[int] = None
    recording_id: str
    tags: List["TagBase"] = []

    class Config:
        from_attributes = True


class TrackReadSimple(TrackBase):
    albums: List[AlbumBase]
    artists: List[ArtistBase]

    class Config:
        from_attributes = True


class TrackRead(TrackReadSimple):
    track_versions: List[TrackVersionBase]

    class Config:
        from_attributes = True


class ArtistRead(ArtistBase):
    discogs_artist_id: Optional[int]
    name_variations: Optional[str] = None
    profile: Optional[str] = None
    albums: Optional[List[AlbumBase]] = []
    album_releases: Optional[List[AlbumReleaseBase]] = []
    tags: List["TagBase"] = []

    class Config:
        from_attributes = True


class AlbumSimple(AlbumBase):
    artists: List[ArtistBase]

    class Config:
        from_attributes = True


class TagBase(BaseModel):
    tag_uuid: UUID
    name: str
    count: Optional[int] = 0

    class Config:
        from_attributes = True


class GenreBase(BaseModel):
    genre_uuid: UUID
    name: str

    class Config:
        from_attributes = True


class AlbumRead(AlbumBase):
    releases: List[AlbumReleaseBase]
    artists: List[ArtistBase]
    tracks: List[TrackBase]
    tags: List[TagBase] = []
    has_digital: bool = False
    class Config:
        from_attributes = True


class CollectionAlbumFormatRead(BaseModel):
    format: str
    status: str

    class Config:
        from_attributes = True


class AlbumFlat(BaseModel):
    album_uuid: UUID
    quality: str
    title: str = Field(alias="title")
    release_date: Optional[datetime]
    image_url: Optional[str]
    image_thumbnail_url: Optional[str]
    artists: List[ArtistBase]
    releases: List[AlbumReleaseBase] = []
    formats: List[CollectionAlbumFormatRead] = Field(
        default_factory=list,
        alias=AliasPath("collectionalbumbridge", 0, "formats"),
    )

    class Config:
        from_attributes = True
        populate_by_name = True


class AlbumReleaseRead(AlbumReleaseBase):
    album: AlbumBase
    artists: List[ArtistBase]
    tracks: List[TrackBase]

    class Config:
        from_attributes = True


class AlbumReleaseSimple(BaseModel):
    album_release_uuid: UUID
    discogs_release_id: Optional[int]

    class Config:
        from_attributes = True


class AlbumInCollection(AlbumSimple):
    formats: List[CollectionAlbumFormatRead] = []

    class Config:
        from_attributes = True


# -------------------------------------------------------------------
# Collections
# -------------------------------------------------------------------

class CollectionBase(BaseModel):
    collection_uuid: UUID
    collection_name: str

    class Config:
        from_attributes = True


class LibraryTrackBase(BaseModel):
    library_track_uuid: UUID
    track_version_uuid: UUID
    path: Optional[str] = None
    quality: Optional[str] = None
    duration_ms: Optional[int] = None
    added_at: datetime

    class Config:
        from_attributes = True


class LibraryTrackRead(LibraryTrackBase):
    track_version: Optional[TrackVersionBase] = None

    class Config:
        from_attributes = True


class CollectionSimple(CollectionBase):
    albums: List[AlbumBase]
    album_releases: List[AlbumReleaseSimple]

    class Config:
        from_attributes = True


class CollectionSimpleRead(CollectionBase):
    albums: list[AlbumFlat]
    tracks: List[LibraryTrackRead]

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    offset: int
    limit: int
    items: List[T]


class CollectionRead(CollectionBase):
    albums: List[AlbumInCollection]
    album_releases: List[AlbumReleaseBase]
    created_at: Optional[datetime]
    tracks: List[LibraryTrackRead]

    class Config:
        from_attributes = True


# -------------------------------------------------------------------
# Search + Playback
# -------------------------------------------------------------------

class MusicSearchResponse(BaseModel):
    albums: List[AlbumRead]
    artists: List[ArtistRead]
    tracks: List[TrackReadSimple]


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
    source: Optional[str]
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


class PlayRequest(BaseModel):
    track_uuid: Optional[UUID] = None
    track_version_uuid: Optional[UUID] = None
    album_uuid: Optional[UUID] = None
    artist_uuid: Optional[UUID] = None

    @root_validator(pre=True)
    def ensure_one_field(cls, values):
        provided = [k for k, v in values.items() if v is not None]
        if len(provided) == 0:
            raise ValueError(
                "One of track_uuid, track_version_uuid, album_uuid, or artist_uuid must be provided"
            )
        if len(provided) > 1:
            raise ValueError(
                "Only one of track_uuid, track_version_uuid, album_uuid, or artist_uuid may be provided"
            )
        return values


class PlaybackQueueItem(BaseModel):
    playback_queue_uuid: UUID
    user_uuid: UUID
    track: TrackReadSimple
    position: int
    added_at: datetime
    added_by: str | None = None
    duration_ms: int | None = None
    file_url: str | None = None

    class Config:
        from_attributes = True


class PlaybackQueueSimple(BaseModel):
    playback_queue_uuid: UUID
    user_uuid: UUID
    tracks: List[PlaybackQueueItem] = Field(default_factory=list)
    next: PlaybackQueueItem | None = None
    previous: PlaybackQueueItem | None = None
    now_playing: PlaybackQueueItem | None = None

    class Config:
        from_attributes = True


class NowPlayingEvent(BaseModel):
    track_uuid: UUID
    track_name: str
    artist_uuid: UUID | None = None
    artist_name: str
    album_uuid: UUID | None = None
    album_name: str
    duration_ms: int | None = None
    file_url: str | None = None
    position_ms: int
    play_state: str


class SeekRequest(BaseModel):
    position_ms: int

