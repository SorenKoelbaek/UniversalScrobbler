from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, UTC,  timezone
from sqlalchemy import BigInteger, Column, String
from typing import Annotated
from uuid import UUID, uuid4
from datetime import datetime, date
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID, FLOAT, INTEGER, DATE
from pgvector.sqlalchemy import Vector

def now_utc_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class TagStyleMatch(SQLModel, table=True):
    __tablename__ = "tag_style_match"
    tag_uuid: UUID = Field(primary_key=True)
    style_uuid: UUID= Field(primary_key=True)

class Style(SQLModel, table=True):
    __tablename__ = "style"
    style_uuid: UUID = Field(primary_key=True)
    style_name: str
    style_description: str
    style_parent_uuid: Optional[UUID] = Field(default=None, foreign_key="style.style_uuid")

class StyleStyleMapping(SQLModel, table=True):
    __tablename__ = "style_style_mapping"
    from_style_uuid: UUID = Field(foreign_key="style.style_uuid", primary_key=True)
    to_style_uuid: UUID = Field(foreign_key="style.style_uuid", primary_key=True)

class TagGenreMapping(SQLModel, table=True):
    __tablename__ = "tag_genre_mapping"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    tag_uuid: UUID = Field(primary_key=True)
    genre_name: Optional[str] = Field(nullable=False)
    style_name: Optional[str] = Field(nullable=False)


class AlbumVector(SQLModel, table=True):
    __tablename__ = "album_vector"

    album_uuid: UUID = Field(primary_key=True, index=True)

    artist_vector: List[float] = Field(sa_column=Column(Vector(512), nullable=False))
    year_vector: List[float] = Field(sa_column=Column(Vector(1), nullable=False))
    type_vector: List[float] = Field(sa_column=Column(Vector(17), nullable=False))
    style_vector_reduced: List[float] = Field(sa_column=Column(Vector(1024), nullable=True))

class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"
    refresh_token_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    user_uuid: UUID = Field(index=True, nullable=False)
    token: str  # store this raw or hashed
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    revoked: bool = Field(default=False)


class SearchIndex(SQLModel, table=True):
    __tablename__ = "search_index"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    entity_uuid: UUID = Field(primary_key=True)
    entity_type: str = Field(sa_column=Column("entity_type", String, nullable=False))
    display_title: str
    search_vector: Optional[str] = Field(
        sa_column=Column("search_vector", TSVECTOR)
    )

class AlbumTagGenreStyleFingerprint(SQLModel, table=True):
    __tablename__ = "album_tag_genre_style_fingerprint"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    album_uuid: UUID = Field(primary_key=True)
    tag_uuid: UUID = Field(primary_key=True)
    style_uuid: UUID = Field(primary_key=True)

    tag_count: int = Field(
        sa_column=Column("tag_count", INTEGER, nullable=False)
    )
    total_count: int = Field(
        sa_column=Column("total_count", INTEGER, nullable=False)
    )
    tag_weight: float = Field(
        sa_column=Column("tag_weight", FLOAT, nullable=False)
    )


class ArtistAlbumTagFingerprint(SQLModel, table=True):
    __tablename__ = "artist_album_tag_fingerprint"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    artist_uuid: UUID = Field(
        sa_column=Column("artist_uuid", PGUUID(as_uuid=True), primary_key=True)
    )
    album_uuid: UUID = Field(
        sa_column=Column("album_uuid", PGUUID(as_uuid=True), primary_key=True)
    )
    album_title: str = Field(nullable=False)
    release_date: date = Field(
        sa_column=Column("release_date", DATE, nullable=False)
    )
    style_uuid: UUID = Field(
        sa_column=Column("style_uuid", PGUUID(as_uuid=True), primary_key=True)
    )
    tag_count: int = Field(
        sa_column=Column("tag_count", INTEGER, nullable=False)
    )
    tag_weight: float = Field(
        sa_column=Column("tag_weight", FLOAT, nullable=False)
    )

class ScrobbleResolutionSearchIndex(SQLModel, table=True):
    __tablename__ = "scrobble_resolution_search_index"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    track_uuid: UUID = Field(primary_key=True)
    track_name: str
    artist_uuid: UUID
    artist_name: str
    album_uuid: UUID
    album_title: str

    track_name_vector: str = Field(sa_column=Column(TSVECTOR), repr=False)
    artist_name_vector: str = Field(sa_column=Column(TSVECTOR), repr=False)
    album_title_vector: str = Field(sa_column=Column(TSVECTOR), repr=False)

class ScrobbleResolutionIndex(SQLModel, table=True):
    __tablename__ = "scrobble_resolution_index"
    __table_args__ = {"info": {"skip_autogenerate": True}}

    track_uuid: UUID = Field( primary_key=True)
    track_name: str
    artist_uuid: UUID
    artist_name: str
    album_uuid: UUID
    album_title: str
    search_vector: str = Field(sa_column=Column(TSVECTOR), repr=False)


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
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    password: str
    spotify_token: Optional["SpotifyToken"] = Relationship(back_populates="user")
    discogs_token: Optional["DiscogsToken"] = Relationship(back_populates="user")
    collections: List["Collection"] = Relationship(back_populates="user")

class TrackVersionTagBridge(SQLModel, table=True):
    __tablename__ = "track_version_tag_bridge"

    track_version_uuid: UUID = Field(foreign_key="track_version.track_version_uuid", primary_key=True)
    tag_uuid: UUID = Field(foreign_key="tag.tag_uuid", primary_key=True)
    count: int = 0  # from MusicBrainz 'count'
    created_at: datetime = Field(default_factory=now_utc_naive, sa_column_kwargs={"server_default": func.now()})

class TrackVersionGenreBridge(SQLModel, table=True):
    __tablename__ = "track_version_genre_bridge"

    track_version_uuid: UUID = Field(foreign_key="track_version.track_version_uuid", primary_key=True)
    genre_uuid: UUID = Field(foreign_key="genre.genre_uuid", primary_key=True)
    count: int = 0  # from MusicBrainz 'count'
    created_at: datetime = Field(default_factory=now_utc_naive, sa_column_kwargs={"server_default": func.now()})

class AlbumTagBridge(SQLModel, table=True):
    __tablename__ = "album_tag_bridge"

    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    tag_uuid: UUID = Field(foreign_key="tag.tag_uuid", primary_key=True)
    count: int = 0

class AlbumGenreBridge(SQLModel, table=True):
    __tablename__ = "album_genre_bridge"

    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    genre_uuid: UUID = Field(foreign_key="genre.genre_uuid", primary_key=True)
    count: int = 0

class AlbumTypeBridge(SQLModel, table=True):
    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    album_type_uuid: UUID = Field(foreign_key="album_type.album_type_uuid", primary_key=True)
    primary: bool = Field(default=False)

class AlbumType(SQLModel, table=True):
    __tablename__ = "album_type"
    album_type_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: Optional[str]
    albums: List["Album"] = Relationship(back_populates="types", link_model=AlbumTypeBridge)
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )

class AlbumReleaseTagBridge(SQLModel, table=True):
    __tablename__ = "album_release_tag_bridge"

    album_release_uuid: UUID = Field(foreign_key="album_release.album_release_uuid", primary_key=True)
    tag_uuid: UUID = Field(foreign_key="tag.tag_uuid", primary_key=True)
    count: int = 0

class ArtistTagBridge(SQLModel, table=True):
    __tablename__ = "artist_tag_bridge"
    artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)
    tag_uuid: UUID = Field(foreign_key="tag.tag_uuid", primary_key=True)
    count: int = 0

class AlbumReleaseGenreBridge(SQLModel, table=True):
    __tablename__ = "album_release_genre_bridge"

    album_release_uuid: UUID = Field(foreign_key="album_release.album_release_uuid", primary_key=True)
    genre_uuid: UUID = Field(foreign_key="genre.genre_uuid", primary_key=True)
    count: int = 0

class Tag(SQLModel, table=True):
    __tablename__ = "tag"

    tag_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=now_utc_naive, sa_column_kwargs={"server_default": func.now()})

    albums: List["Album"] = Relationship(back_populates="tags", link_model=AlbumTagBridge)
    album_releases: List["AlbumRelease"] = Relationship(back_populates="tags", link_model=AlbumReleaseTagBridge)
    # inside Tag:
    track_versions: List["TrackVersion"] = Relationship(back_populates="tags", link_model=TrackVersionTagBridge)
    artists: List["Artist"] = Relationship(back_populates="tags", link_model=ArtistTagBridge)


class Genre(SQLModel, table=True):
    __tablename__ = "genre"

    genre_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=now_utc_naive, sa_column_kwargs={"server_default": func.now()})

    albums: List["Album"] = Relationship(back_populates="genres", link_model=AlbumGenreBridge)
    album_releases: List["AlbumRelease"] = Relationship(back_populates="genres", link_model=AlbumReleaseGenreBridge)
    track_versions: List["TrackVersion"] = Relationship(back_populates="genres", link_model=TrackVersionGenreBridge)

class DiscogsOAuthTemp(SQLModel, table=True):
    __tablename__ = "discogs_oauth_temp"

    oauth_token: str = Field(primary_key=True)
    oauth_token_secret: str
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid", nullable=False)
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )

class SpotifyToken(SQLModel, table=True):
    """Spotify token info linked to a user."""
    __tablename__ = "spotify_token"
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

class DiscogsToken(SQLModel, table=True):
    """Spotify token info linked to a user."""
    __tablename__ = "discogs_token"
    discogs_token_uuid: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        sa_column_kwargs={"unique": True, "server_default": func.gen_random_uuid()},
    )

    user_uuid: UUID = Field(foreign_key="appuser.user_uuid", nullable=False, unique=True)
    access_token: str
    access_token_secret: str
    user: Optional["User"] = Relationship(back_populates="discogs_token")

class ArtistBridge(SQLModel, table=True):
    __tablename__ = "artist_bridge"

    parent_artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)
    child_artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)

class AlbumArtistBridge(SQLModel, table=True):
    __tablename__ = "album_artist_bridge"

    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)

class AlbumReleaseArtistBridge(SQLModel, table=True):
    __tablename__ = "album_release_artist_bridge"

    album_release_uuid: UUID = Field(foreign_key="album_release.album_release_uuid", primary_key=True)
    artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)

class Device(SQLModel, table=True):
    __tablename__ = "device"
    device_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    device_id: str
    device_name: str
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")
    location: Optional[str] = None
    context: Optional[str] = None

class PlaybackHistory(SQLModel, table=True):
    __tablename__ = "playback_history"

    playback_history_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")
    track_version_uuid: Optional[UUID] = Field(foreign_key="track_version.track_version_uuid")
    track_uuid: Optional[UUID] = Field(foreign_key="track.track_uuid")
    album_uuid: Optional[UUID] = Field(foreign_key="album.album_uuid")
    played_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    source: str = "spotify"
    device_uuid: UUID = Field(foreign_key="device.device_uuid")
    device: Optional["Device"] = Relationship()
    full_play: bool = False
    is_still_playing: bool = True
    spotify_track_id: Optional[str] = None
    user: Optional["User"] = Relationship()
    track: Optional["Track"] = Relationship()
    album: Optional["Album"] = Relationship()

class TrackVersionAlbumReleaseBridge(SQLModel, table=True):
    __tablename__ = "track_version_album_release_bridge"

    track_version_uuid: UUID = Field(foreign_key="track_version.track_version_uuid", primary_key=True)
    album_release_uuid: UUID = Field(foreign_key="album_release.album_release_uuid", primary_key=True)
    track_number: Optional[str] = Field(default=None, nullable=True)

class TrackAlbumBridge(SQLModel, table=True):
    __tablename__ = "track_album_bridge"

    track_uuid: UUID = Field(foreign_key="track.track_uuid", primary_key=True)
    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    track_number: Optional[str] = Field(default=None, nullable=True)
    canonical_first: Optional[bool] = Field(default=False, nullable=False, sa_column_kwargs={"server_default": None})


class Album(SQLModel, table=True):
    __tablename__ = "album"

    album_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    styles: Optional[str]
    country: Optional[str]
    release_date: Optional[datetime]
    discogs_master_id: Optional[int]
    discogs_main_release_id: Optional[int] = None
    musicbrainz_release_group_id: Optional[str] = Field(default=None, index=True)
    tracks: List["Track"] = Relationship(back_populates="albums",
                                         link_model=TrackAlbumBridge)  # Use TrackAlbumBridge to link tracks to this album
    tags: List["Tag"] = Relationship(back_populates="albums", link_model=AlbumTagBridge)
    genres: List["Genre"] = Relationship(back_populates="albums", link_model=AlbumGenreBridge)
    types: List["AlbumType"] = Relationship(back_populates="albums", link_model=AlbumTypeBridge)
    artists: List["Artist"] = Relationship(back_populates="albums", link_model=AlbumArtistBridge)
    releases: List["AlbumRelease"] = Relationship(back_populates="album")
    image_url: Optional[str]
    image_thumbnail_url: Optional[str]
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    quality: Optional[str]

class AlbumRelease(SQLModel, table=True):
    __tablename__ = "album_release"
    album_release_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    album_uuid: UUID = Field(foreign_key="album.album_uuid")
    album: Optional["Album"] = Relationship(back_populates="releases")
    title: str
    is_main_release: bool = False
    discogs_release_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger),
        description="Discogs release ID as bigint — may be missing for bootlegs, etc."
    )
    musicbrainz_release_id: Optional[str] = Field(default=None, index=True)  # NEW
    country: Optional[str]
    release_date: Optional[datetime]

    # Define relationship with TrackVersion using SQLModel's Relationship
    track_versions: List["TrackVersion"] = Relationship(
        back_populates="album_releases",
        link_model=TrackVersionAlbumReleaseBridge
    )
    tags: List["Tag"] = Relationship(back_populates="album_releases", link_model=AlbumReleaseTagBridge)
    genres: List["Genre"] = Relationship(back_populates="album_releases", link_model=AlbumReleaseGenreBridge)

    artists: List["Artist"] = Relationship(back_populates="album_releases", link_model=AlbumReleaseArtistBridge)
    image_url: Optional[str]
    image_thumbnail_url: Optional[str]
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    quality: Optional[str]

class TrackArtistBridge(SQLModel, table=True):
    __tablename__ = "track_artist_bridge"

    track_uuid: UUID = Field(foreign_key="track.track_uuid", primary_key=True)
    artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)

class Artist(SQLModel, table=True):
    __tablename__ = "artist"
    musicbrainz_artist_id: Optional[str] = Field(default=None, index=True)
    artist_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    discogs_artist_id: Optional[int]
    name: str
    name_variations: Optional[str]
    profile: Optional[str]
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    albums: List["Album"] = Relationship(back_populates="artists", link_model=AlbumArtistBridge)
    album_releases: Optional[List["AlbumRelease"]] = Relationship(back_populates="artists", link_model=AlbumReleaseArtistBridge)
    # self-referencing links
    members: List["Artist"] = Relationship(
        back_populates="part_of",
        link_model=ArtistBridge,
        sa_relationship_kwargs={"primaryjoin": "Artist.artist_uuid==ArtistBridge.parent_artist_uuid",
                                "secondaryjoin": "Artist.artist_uuid==ArtistBridge.child_artist_uuid"},
    )
    part_of: List["Artist"] = Relationship(
        back_populates="members",
        link_model=ArtistBridge,
        sa_relationship_kwargs={"primaryjoin": "Artist.artist_uuid==ArtistBridge.child_artist_uuid",
                                "secondaryjoin": "Artist.artist_uuid==ArtistBridge.parent_artist_uuid"},
    )
    tracks: List["Track"] = Relationship(
        back_populates="artists",
        link_model=TrackArtistBridge
    )
    tags: List["Tag"] = Relationship(back_populates="artists", link_model=ArtistTagBridge)
    quality: Optional[str]

class Track(SQLModel, table=True):
    __tablename__ = "track"

    track_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    duration: Optional[int] = 0
    albums: List[Album] = Relationship(
        back_populates="tracks", link_model=TrackAlbumBridge
    )
    artists: List["Artist"] = Relationship(
        back_populates="tracks",
        link_model=TrackArtistBridge  # Link to TrackArtistBridge to link artists
    )
    track_versions: List["TrackVersion"] = Relationship(back_populates="track")


class TrackVersionExtraArtist(SQLModel, table=True):
    __tablename__ = "track_version_extra_artist"

    track_version_uuid: UUID = Field(foreign_key="track_version.track_version_uuid", primary_key=True)
    artist_uuid: UUID = Field(foreign_key="artist.artist_uuid", primary_key=True)
    role: Optional[str] = None  # For storing the role (e.g., "Remix", "Producer")
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    track_version: "TrackVersion" = Relationship(back_populates="extra_artists")


class TrackVersion(SQLModel, table=True):
    __tablename__ = "track_version"
    track_version_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    recording_id: Optional[str] = Field(default=None, index=True, unique=False)
    track_uuid: UUID = Field(foreign_key="track.track_uuid")
    duration: Optional[int] = 0
    album_releases: List[AlbumRelease] = Relationship(
        back_populates="track_versions",
        link_model=TrackVersionAlbumReleaseBridge
    )

    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
    quality: Optional[str]
    extra_artists: List[TrackVersionExtraArtist] = Relationship(back_populates="track_version")
    tags: List["Tag"] = Relationship(back_populates="track_versions", link_model=TrackVersionTagBridge)
    genres: List["Genre"] = Relationship(back_populates="track_versions", link_model=TrackVersionGenreBridge)
    track: Optional["Track"] = Relationship(back_populates="track_versions")

class CollectionAlbumBridge(SQLModel, table=True):
    __tablename__ = "collection_album_bridge"
    album_uuid: UUID = Field(foreign_key="album.album_uuid", primary_key=True)
    collection_uuid: UUID = Field(foreign_key="collection.collection_uuid", primary_key=True)


class CollectionAlbumReleaseBridge(SQLModel, table=True):
    __tablename__ = "collection_album_release_bridge"
    collection_uuid: UUID = Field(foreign_key="collection.collection_uuid", primary_key=True)
    album_release_uuid: UUID = Field(foreign_key="album_release.album_release_uuid", primary_key=True)
    album_release: Optional["AlbumRelease"] = Relationship(back_populates=None)


class Collection(SQLModel, table=True):
    __tablename__ = "collection"
    collection_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    collection_name: str
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")
    user: Optional["User"] = Relationship(back_populates="collections")
    albums: List["Album"] = Relationship(link_model=CollectionAlbumBridge)
    album_releases: List["AlbumRelease"] = Relationship(
        link_model=CollectionAlbumReleaseBridge
    )
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )

