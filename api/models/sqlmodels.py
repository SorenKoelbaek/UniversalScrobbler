from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime, UTC,  timezone

from uuid import UUID, uuid4
from datetime import datetime


def now_utc_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
    playback_history: List["PlaybackHistory"] = Relationship(back_populates="user")
    collections: List["Collection"] = Relationship(back_populates="user")


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

class PlaybackHistory(SQLModel, table=True):
    __tablename__ = "playback_history"

    playback_history_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")

    track_uuid: Optional[UUID] = Field(foreign_key="track.track_uuid")
    artist_uuid: Optional[UUID] = Field(foreign_key="artist.artist_uuid")
    album_uuid: Optional[UUID] = Field(foreign_key="album.album_uuid")
    album_release_uuid: Optional[UUID] = Field(foreign_key="album_release.album_release_uuid")
    spotify_track_id: Optional[str]
    played_at: datetime
    source: str = "spotify"
    device_name: Optional[str] = None
    duration_ms: Optional[int] = None
    progress_ms: Optional[int] = None
    full_play: bool = False
    is_still_playing: bool = False

    user: Optional["User"] = Relationship(back_populates="playback_history")
    track: Optional["Track"] = Relationship()
    artist: Optional["Artist"] = Relationship()
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


class Album(SQLModel, table=True):
    __tablename__ = "album"

    album_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    styles: Optional[str]
    country: Optional[str]
    release_date: Optional[datetime]
    discogs_master_id: Optional[int]
    discogs_main_release_id: Optional[int] = None
    tracks: List["Track"] = Relationship(back_populates="albums",
                                         link_model=TrackAlbumBridge)  # Use TrackAlbumBridge to link tracks to this album

    artists: List["Artist"] = Relationship(back_populates="albums", link_model=AlbumArtistBridge)
    releases: List["AlbumRelease"] = Relationship(back_populates="album")
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
    discogs_release_id: Optional[int]  # maybe a release doesn't have to exist on Discogs? - bootlegs?
    country: Optional[str]
    release_date: Optional[datetime]

    # Define relationship with TrackVersion using SQLModel's Relationship
    track_versions: List["TrackVersion"] = Relationship(
        back_populates="album_releases",
        link_model=TrackVersionAlbumReleaseBridge
    )

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
    quality: Optional[str]


class Track(SQLModel, table=True):
    __tablename__ = "track"

    track_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    albums: List[Album] = Relationship(
        back_populates="tracks", link_model=TrackAlbumBridge
    )
    artists: List["Artist"] = Relationship(
        back_populates="tracks",
        link_model=TrackArtistBridge  # Link to TrackArtistBridge to link artists
    )


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
    track_uuid: UUID = Field(foreign_key="track.track_uuid")
    duration: Optional[str]  # optionally a time-aspect instead?

    # Define relationship with AlbumRelease using SQLModel's Relationship
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