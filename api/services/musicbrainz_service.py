import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select
from uuid import UUID
from datetime import datetime, date
from typing import Optional, Tuple
import re
from uuid import uuid4
from sqlmodel import select
from sqlalchemy.dialects.postgresql import insert

from dependencies.musicbrainz_api import MusicBrainzAPI
from models.sqlmodels import (
    Album,
    AlbumRelease,
    Track,
    TrackVersion,
    Artist,
    Tag,
    Genre,
    AlbumArtistBridge,
    AlbumReleaseArtistBridge,
    TrackArtistBridge,
    TrackVersionExtraArtist,
    TrackVersionTagBridge,
    TrackAlbumBridge,
    TrackVersionAlbumReleaseBridge,
    AlbumReleaseGenreBridge,
    AlbumReleaseTagBridge, AlbumTagBridge, AlbumGenreBridge, CollectionAlbumBridge, CollectionAlbumReleaseBridge
)
from dependencies.cover_art_archive_api import CoverArtArchiveAPI

cover_art_archive = CoverArtArchiveAPI()
from config import settings
import logging
import re
import unicodedata
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)



def fuzzy_match_title(candidate: str, choices: list[str], threshold: int = 90) -> str | None:
    for c in choices:
        score = fuzz.ratio(candidate, c)
        if score >= threshold:
            return c
    return None



def normalize_title(title: str) -> str:
    """
    Normalize track/album titles for robust matching.
    - Lowercase
    - Strip whitespace
    - Collapse multiple spaces
    - Remove diacritics
    - Standardize apostrophes/quotes
    - Remove punctuation in parentheses like (skit), (intro)
    - Replace separators (/,&,+,-,–,—,.,,) with spaces
    - Remove other non-alphanumeric except spaces
    """
    if not title:
        return ""

    # Unicode normalize + strip diacritics
    s = unicodedata.normalize("NFKD", title)
    s = "".join(c for c in s if not unicodedata.combining(c))

    # Lowercase
    s = s.lower()

    # Standardize apostrophes/quotes
    s = (
        s.replace("’", "'")
         .replace("‘", "'")
         .replace("“", '"')
         .replace("”", '"')
    )

    # Remove parentheticals (skit), (intro), etc.
    s = re.sub(r"\([^)]*\)", "", s)

    # Replace common separators with space
    s = re.sub(r"[\/&\+\-\–\—,:;]", " ", s)

    # Remove other non-alphanumeric (keep spaces)
    s = re.sub(r"[^a-z0-9\s]", "", s)

    # Collapse spaces
    s = re.sub(r"\s+", " ", s).strip()

    return s


def parse_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except Exception:
        return None

class MusicBrainzService:
    def __init__(self, db: AsyncSession, api: MusicBrainzAPI, artist_cache: Optional[dict[str, UUID]] = None, album_cache: Optional[dict[str, UUID]] = None, tag_cache: Optional[dict[str, UUID]] = None):
        self.db = db
        self.api = api
        self.artist_cache = artist_cache or {}
        self.album_cache = album_cache or {}
        self.tag_cache = tag_cache or {}

    async def get_or_create_tag_simple(self, name: str) -> Tag:
        normalized = self.normalize_tag_name(name)

        # Cache hit
        tag_uuid = self.tag_cache.get(normalized)
        if tag_uuid:
            return Tag(tag_uuid=tag_uuid)

        # Create new tag
        tag = Tag(name=normalized)
        self.db.add(tag)
        await self.db.flush()

        # Update cache for future use
        self.tag_cache[normalized] = tag.tag_uuid
        return tag

    # Tag and Genre Creation
    async def get_or_create_tag(self, name: str, cache: Optional[dict] = None) -> Tag:
        key = name.strip().lower()
        if cache is not None and key in cache:
            return cache[key]

        result = await self.db.execute(select(Tag).where(Tag.name == name))
        tag = result.scalar_one_or_none()
        if tag:
            if cache is not None:
                cache[key] = tag
            return tag

        tag = Tag(name=name)
        self.db.add(tag)
        await self.db.flush()
        if cache is not None:
            cache[key] = tag
        return tag

    async def get_or_create_genre(self, name: str) -> Genre:
        result = await self.db.execute(select(Genre).where(Genre.name == name))
        genre = result.scalar_one_or_none()
        if genre:
            return genre
        genre = Genre(name=name)
        self.db.add(genre)
        await self.db.flush()
        return genre

    async def get_or_create_artist_by_name_simple(
            self,
            name: str,
            musicbrainz_artist_id: str = None
    ) -> Artist:
        if not musicbrainz_artist_id:
            raise ValueError(f"Missing MusicBrainz ID for artist: {name}")

        artist_uuid = self.artist_cache.get(musicbrainz_artist_id)
        if not artist_uuid:
            raise ValueError(f"Artist with MBID {musicbrainz_artist_id} not found in preload cache")

        return Artist(artist_uuid=artist_uuid)

    async def get_or_create_artist_by_name(
            self,
            name: str,
            musicbrainz_artist_id: str = None,
            cache: Optional[dict] = None
    ) -> Artist:

        key = musicbrainz_artist_id or name.strip().lower()
        if cache and key in cache:
            return cache[key]

        if not musicbrainz_artist_id:
            result = await self.db.execute(select(Artist).where(Artist.name == name))
            artist = result.scalar_one_or_none()
        else:
            result = await self.db.execute(select(Artist).where(Artist.musicbrainz_artist_id == musicbrainz_artist_id))
            artist = result.scalar_one_or_none()

        if artist:
            if cache is not None:
                cache[key] = artist
            return artist

        artist = Artist(name=name, musicbrainz_artist_id=musicbrainz_artist_id)
        self.db.add(artist)
        await self.db.flush()

        if cache is not None:
            cache[key] = artist

        return artist

    def normalize_tag_name(self, name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[\.\-_]", " ", name)  # replace punctuation with spaces
        name = re.sub(r"\s+", " ", name)  # collapse multiple spaces
        name = name.replace("&", "and")  # common synonym
        return name.strip()


    async def get_or_create_album_from_release_group_simple(self, release_group_data: dict) -> Album:
        musicbrainz_id = release_group_data["id"]
        album_uuid = self.album_cache.get(musicbrainz_id)

        if album_uuid:
            return Album(album_uuid=album_uuid)
        # Create the album object without the tags field
        album = Album(
            title=release_group_data["title"],
            musicbrainz_release_group_id=musicbrainz_id,
            release_date=parse_date(release_group_data.get("first-release-date")),
            quality="normal",
            country=None
        )
        self.db.add(album)
        await self.db.flush()

        for credit in release_group_data.get("artist-credit", []):
            artist_data = credit.get("artist")
            if artist_data:
                artist = await self.get_or_create_artist_by_name(artist_data["name"], artist_data.get("id"))
                result = await self.db.execute(
                    select(AlbumArtistBridge)
                    .where(AlbumArtistBridge.album_uuid == album.album_uuid, AlbumArtistBridge.artist_uuid == artist.artist_uuid))
                existing_relation = result.scalar_one_or_none()
                if not existing_relation:
                    self.db.add(AlbumArtistBridge(album_uuid=album.album_uuid, artist_uuid=artist.artist_uuid))

        # Add tags to the album using the AlbumTagBridge
        for tag in release_group_data.get("tags", []):
            tag_name = self.normalize_tag_name(tag["name"])
            tag_obj = await self.get_or_create_tag_simple(tag_name)
            # Check if the tag already exists in the database
            result = await self.db.execute(
                select(AlbumTagBridge)
                .where(AlbumTagBridge.album_uuid == album.album_uuid, AlbumTagBridge.tag_uuid == tag_obj.tag_uuid))
            existing_tag = result.scalar_one_or_none()
            if not existing_tag:
                self.db.add(AlbumTagBridge(
                    album_uuid=album.album_uuid,
                    tag_uuid=tag_obj.tag_uuid,
                    count=tag.get("count", 0)
                ))

        # Add genres to the album using the AlbumGenreBridge
        for genre in release_group_data.get("genres", []):
            genre_name = self.normalize_tag_name(genre["name"])
            genre_obj = await self.get_or_create_genre(genre_name)
            # Check if the genre already exists in the database
            result = await self.db.execute(
                select(AlbumGenreBridge)
                .where(
            AlbumGenreBridge.album_uuid == album.album_uuid,
                        AlbumGenreBridge.genre_uuid == genre_obj.genre_uuid))
            existing_genre = result.scalar_one_or_none()
            if not existing_genre:
                self.db.add(AlbumGenreBridge(
                    album_uuid=album.album_uuid,
                    genre_uuid=genre_obj.genre_uuid,
                    count=genre.get("count", 0)
                ))

        return album

    # Create Album from Release Group
    async def get_or_create_album_from_release_group(self, release_group_data: dict) -> Album:
        musicbrainz_id = release_group_data["id"]
        result = await self.db.execute(
            select(Album)
            .where(Album.musicbrainz_release_group_id == musicbrainz_id)
            .options(
                selectinload(Album.artists),
                selectinload(Album.tags),
                selectinload(Album.genres),
                selectinload(Album.tracks),
                selectinload(Album.releases)
            )
        )
        album = result.scalar_one_or_none()
        if album:
            return album

        # Create the album object without the tags field
        album = Album(
            title=release_group_data["title"],
            musicbrainz_release_group_id=musicbrainz_id,
            release_date=parse_date(release_group_data.get("first-release-date")),
            quality="normal",
            country=None
        )
        self.db.add(album)
        await self.db.flush()

        for credit in release_group_data.get("artist-credit", []):
            artist_data = credit.get("artist")
            if artist_data:
                artist = await self.get_or_create_artist_by_name(artist_data["name"], artist_data.get("id"))
                result = await self.db.execute(
                    select(AlbumArtistBridge)
                    .where(AlbumArtistBridge.album_uuid == album.album_uuid, AlbumArtistBridge.artist_uuid == artist.artist_uuid))
                existing_relation = result.scalar_one_or_none()
                if not existing_relation:
                    self.db.add(AlbumArtistBridge(album_uuid=album.album_uuid, artist_uuid=artist.artist_uuid))

        # Add tags to the album using the AlbumTagBridge
        for tag in release_group_data.get("tags", []):
            tag_name = self.normalize_tag_name(tag["name"])
            tag_obj = await self.get_or_create_tag(tag_name)
            # Check if the tag already exists in the database
            result = await self.db.execute(
                select(AlbumTagBridge)
                .where(AlbumTagBridge.album_uuid == album.album_uuid, AlbumTagBridge.tag_uuid == tag_obj.tag_uuid))
            existing_tag = result.scalar_one_or_none()
            if not existing_tag:
                self.db.add(AlbumTagBridge(
                    album_uuid=album.album_uuid,
                    tag_uuid=tag_obj.tag_uuid,
                    count=tag.get("count", 0)
                ))

        # Add genres to the album using the AlbumGenreBridge
        for genre in release_group_data.get("genres", []):
            genre_name = self.normalize_tag_name(genre["name"])
            genre_obj = await self.get_or_create_genre(genre_name)
            # Check if the genre already exists in the database
            result = await self.db.execute(
                select(AlbumGenreBridge)
                .where(
            AlbumGenreBridge.album_uuid == album.album_uuid,
                        AlbumGenreBridge.genre_uuid == genre_obj.genre_uuid))
            existing_genre = result.scalar_one_or_none()
            if not existing_genre:
                self.db.add(AlbumGenreBridge(
                    album_uuid=album.album_uuid,
                    genre_uuid=genre_obj.genre_uuid,
                    count=genre.get("count", 0)
                ))

        album_with_relations = await self.db.execute(
            select(Album)
            .options(
                selectinload(Album.artists),
                selectinload(Album.tags),
                selectinload(Album.genres),
                selectinload(Album.tracks),
                selectinload(Album.releases)
            )
            .where(Album.album_uuid == album.album_uuid)
        )
        return album_with_relations.scalar_one()

    async def create_album_release_simple(self, album: Album, data: dict, discogs_release_id: int = None) -> AlbumRelease:
        musicbrainz_release_id = data["id"]
        result = await self.db.execute(
            select(AlbumRelease)
            .where(AlbumRelease.musicbrainz_release_id == musicbrainz_release_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        release_date = parse_date(data.get("date"))
        album_release = AlbumRelease(
            album_uuid=album.album_uuid,
            title=data["title"],
            country=data.get("country"),
            release_date=release_date,
            musicbrainz_release_id=musicbrainz_release_id,
            discogs_release_id=discogs_release_id,
            image_url=None,
            image_thumbnail_url=None,
        )
        self.db.add(album_release)
        await self.db.flush()

        for credit in data.get("artist-credit", []):
            artist_data = credit.get("artist")
            if artist_data:

                artist = await self.get_or_create_artist_by_name_simple(artist_data["name"], artist_data.get("id"))
                stmt = insert(AlbumReleaseArtistBridge).values(
                    album_release_uuid=album_release.album_release_uuid,
                    artist_uuid=artist.artist_uuid
                ).on_conflict_do_nothing()
                await self.db.execute(stmt)


        # Add tags to the album release using the AlbumReleaseTagBridge
        for tag in data.get("tags", []):
            tag_name = self.normalize_tag_name(tag["name"])
            tag_obj = await self.get_or_create_tag_simple(tag_name)
            # Check if the tag already exists in the database
            result = await self.db.execute(
                select(AlbumReleaseTagBridge)
                .where(AlbumReleaseTagBridge.album_release_uuid == album_release.album_release_uuid,
                       AlbumReleaseTagBridge.tag_uuid == tag_obj.tag_uuid))
            existing_tag = result.scalar_one_or_none()
            if not existing_tag:
                self.db.add(AlbumReleaseTagBridge(
                    album_release_uuid=album_release.album_release_uuid,
                    tag_uuid=tag_obj.tag_uuid,
                    count=tag.get("count", 0)
                ))

        # Add genres to the album release using the AlbumReleaseGenreBridge
        for genre in data.get("genres", []):
            genre_name = self.normalize_tag_name(genre["name"])
            genre_obj = await self.get_or_create_genre(genre_name)
            # Check if the genre already exists in the database
            result = await self.db.execute(
                select(AlbumReleaseGenreBridge)
                .where(AlbumReleaseGenreBridge.album_release_uuid == album_release.album_release_uuid,
                       AlbumReleaseGenreBridge.genre_uuid == genre_obj.genre_uuid))
            existing_genre = result.scalar_one_or_none()
            if not existing_genre:
                self.db.add(AlbumReleaseGenreBridge(
                    album_release_uuid=album_release.album_release_uuid,
                    genre_uuid=genre_obj.genre_uuid,
                    count=genre.get("count", 0)
                ))
        return album_release

    # Create Album Release
    async def create_album_release(self, album: Album, data: dict, discogs_release_id: int=None) -> AlbumRelease:
        musicbrainz_release_id = data["id"]
        result = await self.db.execute(
            select(AlbumRelease)
            .where(AlbumRelease.musicbrainz_release_id == musicbrainz_release_id)
            .options(
                selectinload(AlbumRelease.artists),
                selectinload(AlbumRelease.tags),
                selectinload(AlbumRelease.genres),
                selectinload(AlbumRelease.album),
                selectinload(AlbumRelease.track_versions)
            )

        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        release_date = parse_date(data.get("date"))
        album_release = AlbumRelease(
            album=album,
            title=data["title"],
            country=data.get("country"),
            release_date=release_date,
            musicbrainz_release_id=musicbrainz_release_id,
            discogs_release_id=discogs_release_id,
            image_url=None,
            image_thumbnail_url=None,
        )
        self.db.add(album_release)
        await self.db.flush()

        for credit in data.get("artist-credit", []):
            artist_data = credit.get("artist")
            if artist_data:
                artist = await self.get_or_create_artist_by_name(artist_data["name"], artist_data.get("id"))
                self.db.add(AlbumReleaseArtistBridge(
                    album_release_uuid=album_release.album_release_uuid,
                    artist_uuid=artist.artist_uuid
                ))

        # Add tags to the album release using the AlbumReleaseTagBridge
        for tag in data.get("tags", []):
            tag_name = self.normalize_tag_name(tag["name"])
            tag_obj = await self.get_or_create_tag(tag_name)
            # Check if the tag already exists in the database
            result = await self.db.execute(
                select(AlbumReleaseTagBridge)
                .where(AlbumReleaseTagBridge.album_release_uuid == album_release.album_release_uuid,
                    AlbumReleaseTagBridge.tag_uuid == tag_obj.tag_uuid))
            existing_tag = result.scalar_one_or_none()
            if not existing_tag:
                self.db.add(AlbumReleaseTagBridge(
                    album_release_uuid=album_release.album_release_uuid,
                    tag_uuid=tag_obj.tag_uuid,
                    count=tag.get("count", 0)
                ))

        # Add genres to the album release using the AlbumReleaseGenreBridge
        for genre in data.get("genres", []):
            genre_name = self.normalize_tag_name(genre["name"])
            genre_obj = await self.get_or_create_genre(genre_name)
            # Check if the genre already exists in the database
            result = await self.db.execute(
                select(AlbumReleaseGenreBridge)
                .where(AlbumReleaseGenreBridge.album_release_uuid == album_release.album_release_uuid,
                    AlbumReleaseGenreBridge.genre_uuid == genre_obj.genre_uuid))
            existing_genre = result.scalar_one_or_none()
            if not existing_genre:
                self.db.add(AlbumReleaseGenreBridge(
                    album_release_uuid=album_release.album_release_uuid,
                    genre_uuid=genre_obj.genre_uuid,
                    count=genre.get("count", 0)
                ))

        # Load relationships before returning
        album_release_with_relations = await self.db.execute(
            select(AlbumRelease)
            .options(
                selectinload(AlbumRelease.artists),
                selectinload(AlbumRelease.tags),
                selectinload(AlbumRelease.genres),
                selectinload(AlbumRelease.album),
                selectinload(AlbumRelease.track_versions)
            )
            .where(AlbumRelease.album_release_uuid == album_release.album_release_uuid)
        )
        return album_release_with_relations.scalar_one()

    # Create Tracks and Versions
    async def create_tracks_and_versions(
            self,
            album: Album,
            album_release: AlbumRelease,
            media_tracks: list[dict],
            recordings_data: list[dict],  # Pass the list to be converted into the mapping
            should_take_duration: bool = False
    ):
        # Create the recordings_by_id dictionary
        recordings_by_id = {recording["recording_id"]: recording for recording in recordings_data}

        for track_data in media_tracks:
            title = track_data["title"]
            recording_data = track_data["recording"]
            recording_id = recording_data["id"]
            length = track_data.get("length")
            track_number = track_data.get("number")

            # Fetch the full recording data using recordings_by_id
            recording_details = recordings_by_id.get(recording_id, {})

            # Track creation (by title + duration)
            # Track creation (scoped to album by TrackAlbumBridge)
            result = await self.db.execute(
                select(Track)
                .join(TrackAlbumBridge, Track.track_uuid == TrackAlbumBridge.track_uuid)
                .where(
                    Track.name == title,
                    Track.duration == length,
                    TrackAlbumBridge.album_uuid == album.album_uuid
                )
            )
            track = result.scalars().first()  # ✅ avoids crash

            if not track:
                track = Track(name=title, duration=length if length else None)
                self.db.add(track)
                await self.db.flush()

                # Always link Track ↔ Album
                self.db.add(TrackAlbumBridge(
                    track_uuid=track.track_uuid,
                    album_uuid=album.album_uuid,
                    track_number=track_number
                ))

            if not track:
                track = Track(name=title, duration=length if length else None)
                self.db.add(track)
                await self.db.flush()

            # 🔑 Always ensure Track ↔ Album link
            result = await self.db.execute(
                select(TrackAlbumBridge).where(
                    TrackAlbumBridge.track_uuid == track.track_uuid,
                    TrackAlbumBridge.album_uuid == album.album_uuid
                )
            )
            if not result.scalar_one_or_none():
                self.db.add(TrackAlbumBridge(
                    track_uuid=track.track_uuid,
                    album_uuid=album.album_uuid,
                    track_number=track_number
                ))

            # TrackVersion creation
            result = await self.db.execute(
                select(TrackVersion).where(TrackVersion.recording_id == recording_id)
            )
            version = result.scalar_one_or_none()
            if not version:
                version = TrackVersion(
                    recording_id=recording_id,
                    track_uuid=track.track_uuid,
                    duration=length if length else None,
                    quality="normal",
                )
                self.db.add(version)
                await self.db.flush()

            # Link Version ↔ AlbumRelease
            result = await self.db.execute(
                select(TrackVersionAlbumReleaseBridge).where(
                    TrackVersionAlbumReleaseBridge.track_version_uuid == version.track_version_uuid,
                    TrackVersionAlbumReleaseBridge.album_release_uuid == album_release.album_release_uuid
                )
            )
            if not result.scalar_one_or_none():
                self.db.add(TrackVersionAlbumReleaseBridge(
                    track_version_uuid=version.track_version_uuid,
                    album_release_uuid=album_release.album_release_uuid,
                    track_number=track_number
                ))

            # Link Track ↔ Artists from Album
            album_artists_result = await self.db.execute(
                select(Artist).join(AlbumArtistBridge).where(AlbumArtistBridge.album_uuid == album.album_uuid)
            )
            album_artists = album_artists_result.scalars().all()
            for artist in album_artists:
                result = await self.db.execute(
                    select(TrackArtistBridge).where(
                        TrackArtistBridge.track_uuid == track.track_uuid,
                        TrackArtistBridge.artist_uuid == artist.artist_uuid
                    )
                )
                if not result.scalar_one_or_none():
                    self.db.add(TrackArtistBridge(
                        track_uuid=track.track_uuid,
                        artist_uuid=artist.artist_uuid
                    ))

            # Add extra artists for the track version
            for credit in recording_details.get("artist-credit", []):
                artist_data = credit.get("artist")
                if artist_data:
                    artist = await self.get_or_create_artist_by_name(artist_data["name"])
                    result = await self.db.execute(
                        select(TrackVersionExtraArtist).where(
                            TrackVersionExtraArtist.track_version_uuid == version.track_version_uuid,
                            TrackVersionExtraArtist.artist_uuid == artist.artist_uuid
                        )
                    )
                    if not result.scalar_one_or_none():
                        self.db.add(TrackVersionExtraArtist(
                            track_version_uuid=version.track_version_uuid,
                            artist_uuid=artist.artist_uuid,
                            role=None
                        ))

            # Add tags to the track version
            for tag in recording_details.get("tags", []):
                tag_obj = await self.get_or_create_tag(tag["name"])
                result = await self.db.execute(
                    select(TrackVersionTagBridge).where(
                        TrackVersionTagBridge.track_version_uuid == version.track_version_uuid,
                        TrackVersionTagBridge.tag_uuid == tag_obj.tag_uuid
                    )
                )
                if not result.scalar_one_or_none():
                    self.db.add(TrackVersionTagBridge(
                        track_version_uuid=version.track_version_uuid,
                        tag_uuid=tag_obj.tag_uuid,
                        count=tag.get("count", 0)
                    ))

    async def create_tracks_and_versions_simple(
            self,
            album: Album,
            album_release: AlbumRelease,
            media_tracks: list[dict],
            recordings_data: list[dict],
            should_take_duration: bool = False
    ):
        track_buffer: dict[tuple[str, int | None], Track] = {}
        version_buffer: dict[str, TrackVersion] = {}
        track_album_bridge_buffer: set[tuple[UUID, UUID, str]] = set()
        version_release_bridge_buffer: set[tuple[UUID, UUID, str]] = set()
        track_artist_bridge_buffer: set[tuple[UUID, UUID]] = set()
        extra_artist_bridge_buffer: set[tuple[UUID, UUID]] = set()
        version_tag_bridge_buffer: list[dict] = []

        recordings_by_id = {rec["recording_id"]: rec for rec in recordings_data}
        used_artists = []
        used_tags = []
        # Preload album artists
        album_artists_result = await self.db.execute(
            select(Artist).join(AlbumArtistBridge).where(AlbumArtistBridge.album_uuid == album.album_uuid)
        )
        album_artists = album_artists_result.scalars().all()
        album_artist_ids = {a.artist_uuid for a in album_artists}

        # Caches to avoid redundant SELECTs
        existing_tracks = {}
        existing_versions = {}
        existing_bridges = set()
        existing_extra_artists = set()
        existing_tags = set()

        for track_data in media_tracks:
            title = track_data["title"]
            recording_data = track_data["recording"]
            recording_id = recording_data["id"]
            length = track_data.get("length")
            track_number = track_data.get("number")

            recording_details = recordings_by_id.get(recording_id, {})

            # Track: get or create by name AND duration
            track_key = (title, length)
            track = existing_tracks.get(track_key)

            if not track:
                track = track_buffer.get(track_key)
                if not track:
                    track = Track(track_uuid=uuid4(), name=title, duration=length)
                    track_buffer[track_key] = track

            existing_tracks[track_key] = track


            # Track ↔ Album
            bridge_key = (track.track_uuid, album.album_uuid)
            if bridge_key not in existing_bridges:
                track_album_bridge_buffer.add((track.track_uuid, album.album_uuid, track_number))
                existing_bridges.add(bridge_key)

            # TrackVersion: get or create
            version = existing_versions.get(recording_id)

            if not version:
                version = version_buffer.get(recording_id)
                if not version:
                    version = TrackVersion(
                        track_version_uuid=uuid4(),
                        recording_id=recording_id,
                        track_uuid=track.track_uuid,
                        duration=length if length else None,
                        quality="normal"
                    )
                    version_buffer[recording_id] = version

                existing_versions[recording_id] = version

            # Version ↔ AlbumRelease
            bridge_key = (version.track_version_uuid, album_release.album_release_uuid)
            if bridge_key not in existing_bridges:
                version_release_bridge_buffer.add(
                    (version.track_version_uuid, album_release.album_release_uuid, track_number)
                )

                existing_bridges.add(bridge_key)

            # Track ↔ Artists (Album)
            for artist_uuid in album_artist_ids:
                bridge_key = (track.track_uuid, artist_uuid)
                if bridge_key not in existing_bridges:
                    track_artist_bridge_buffer.add((track.track_uuid, artist_uuid))
                    existing_bridges.add(bridge_key)

            for credit in recording_details.get("artist-credit", []):
                artist_data = credit.get("artist")
                if artist_data:
                    artist = await self.get_or_create_artist_by_name_simple(
                        artist_data["name"],
                        artist_data.get("id")
                    )
                    used_artists.append(artist)
                    key = (version.track_version_uuid, artist.artist_uuid)
                    if key not in existing_extra_artists:
                        extra_artist_bridge_buffer.add((version.track_version_uuid, artist.artist_uuid))
                        existing_extra_artists.add(key)

            from sqlalchemy.dialects.postgresql import insert

            # Tags (normalize tag name)
            for tag in recording_details.get("tags", []):
                tag_name = self.normalize_tag_name(tag["name"])
                tag_obj = await self.get_or_create_tag_simple(tag_name)
                used_tags.append(tag_obj)
                key = (version.track_version_uuid, tag_obj.tag_uuid)

                if key not in existing_tags:
                    version_tag_bridge_buffer.append({
                        "track_version_uuid": version.track_version_uuid,
                        "tag_uuid": tag_obj.tag_uuid,
                        "count": tag.get("count", 0),
                        "created_at": datetime.utcnow(),
                    })
                    existing_tags.add(key)
        if track_buffer:
            self.db.add_all(track_buffer.values())
            await self.db.flush()
        for track_uuid, album_uuid, track_number in track_album_bridge_buffer:
            stmt = insert(TrackAlbumBridge).values(
                track_uuid=track_uuid,
                album_uuid=album_uuid,
                track_number=track_number
            ).on_conflict_do_nothing()
            await self.db.execute(stmt)
        for track_uuid, artist_uuid in track_artist_bridge_buffer:
            stmt = insert(TrackArtistBridge).values(
                track_uuid=track_uuid,
                artist_uuid=artist_uuid
            ).on_conflict_do_nothing()
            await self.db.execute(stmt)

        if version_buffer:
            self.db.add_all(version_buffer.values())
            await self.db.flush()

        for row in version_tag_bridge_buffer:
            stmt = insert(TrackVersionTagBridge).values(**row).on_conflict_do_nothing()
            await self.db.execute(stmt)

        for version_uuid, album_release_uuid, track_number in version_release_bridge_buffer:
            stmt = insert(TrackVersionAlbumReleaseBridge).values(
                track_version_uuid=version_uuid,
                album_release_uuid=album_release_uuid,
                track_number=track_number
            ).on_conflict_do_nothing()
            await self.db.execute(stmt)

        for version_uuid, artist_uuid in extra_artist_bridge_buffer:
            stmt = insert(TrackVersionExtraArtist).values(
                track_version_uuid=version_uuid,
                artist_uuid=artist_uuid,
                role=None
            ).on_conflict_do_nothing()
            await self.db.execute(stmt)

        return used_artists, []

    async def get_or_create_track_version(
            self,
            release_id: str,
            title: str,
            mb_trackid: Optional[str] = None,
    ) -> Optional[TrackVersion]:
        """
        Return an existing TrackVersion for a given release.
        Priority:
          1. MB recording_id
          2. Exact normalized title match
          3. Fuzzy normalized title match
        Never calls MusicBrainz API.
        """

        # Step 1: Fetch release UUID
        result = await self.db.execute(
            select(AlbumRelease.album_release_uuid).where(
                AlbumRelease.musicbrainz_release_id == release_id
            )
        )
        album_release_uuid = result.scalar_one_or_none()
        if not album_release_uuid:
            logger.warning(f"No AlbumRelease found in DB for release {release_id}")
            return None

        # Step 2: Preload all track_versions + tracks for this release
        result = await self.db.execute(
            select(TrackVersion, Track)
            .join(Track, Track.track_uuid == TrackVersion.track_uuid)
            .join(
                TrackVersionAlbumReleaseBridge,
                TrackVersionAlbumReleaseBridge.track_version_uuid == TrackVersion.track_version_uuid,
            )
            .where(TrackVersionAlbumReleaseBridge.album_release_uuid == album_release_uuid)
        )
        rows: list[tuple[TrackVersion, Track]] = result.all()
        if not rows:
            logger.warning(f"No TrackVersions linked for release {release_id}")
            return None

        # 1. MBID match
        if mb_trackid:
            for tv, _ in rows:
                if tv.recording_id == mb_trackid:
                    return tv

        # Prepare normalized names
        title_norm = normalize_title(title)
        name_map = {normalize_title(track.name): (tv, track) for tv, track in rows}

        # 2. Exact normalized match
        if title_norm in name_map:
            tv, track = name_map[title_norm]
            return tv

        # 3. Fuzzy match
        best = fuzzy_match_title(title_norm, list(name_map.keys()))
        if best:
            tv, track = name_map[best]
            logger.info(
                f"Fuzzy matched '{title}' -> '{track.name}' "
                f"(score vs norm: {best})"
            )
            return tv

        # 4. Failure
        logger.warning(f"No track_version match for '{title}' on release {release_id}")
        return None

    async def get_or_create_album_from_musicbrainz_release(
            self,
            musicbrainz_release_id: str,
            discogs_release_id: int = None,
            should_take_duration: bool = False
    ) -> Tuple[Album, AlbumRelease]:
        result = await self.db.execute(
            select(AlbumRelease)
            .where(AlbumRelease.musicbrainz_release_id == musicbrainz_release_id)
            .options(selectinload(AlbumRelease.album).selectinload(Album.artists))
        )
        album_release = result.scalar_one_or_none()
        if album_release:
            return album_release.album, album_release

        release_data = await self.api.get_release(musicbrainz_release_id)
        await asyncio.sleep(1)
        release_group = await self.api.get_release_group_by_release_id(musicbrainz_release_id)
        await asyncio.sleep(1)
        recordings_data = await self.api.get_recordings_for_release(musicbrainz_release_id)

        album = await self.get_or_create_album_from_release_group(release_group)
        album_release = await self.create_album_release(album, release_data, discogs_release_id)

        # add images
        album = await self.fetch_album_image(album, cover_art_archive)
        album_release = await self.fetch_album_release_image(album_release, cover_art_archive)

        for media in release_data.get("media", []):
            await self.create_tracks_and_versions(
                album,
                album_release,
                media.get("tracks", []),
                recordings_data,
                should_take_duration,
            )

        await self.db.commit()

        return album, album_release

    async def clone_album_release_with_links(self,
            original_album_release_uuid: UUID,
            new_discogs_release_id: int,
    ) -> AlbumRelease:
        # Step 1: Fetch the original AlbumRelease with all necessary relationships eagerly loaded
        result = await self.db.execute(
            select(AlbumRelease)
            .where(AlbumRelease.album_release_uuid == original_album_release_uuid)
            .options(
                selectinload(AlbumRelease.artists),
                selectinload(AlbumRelease.track_versions),
                selectinload(AlbumRelease.tags),
                selectinload(AlbumRelease.genres),
            )
        )
        original = result.scalar_one()

        # Step 2: Create the clone of the AlbumRelease
        clone = AlbumRelease(
            album_uuid=original.album_uuid,
            title=original.title,
            is_main_release=False,
            discogs_release_id=new_discogs_release_id,
            musicbrainz_release_id=original.musicbrainz_release_id,
            country=original.country,
            release_date=original.release_date,
            image_url=original.image_url,
            image_thumbnail_url=original.image_thumbnail_url,
            quality=original.quality,
        )
        self.db.add(clone)
        await self.db.flush()  # Assign UUID

        # Step 3: Clone Artist links
        for artist in original.artists:
            self.db.add(AlbumReleaseArtistBridge(
                album_release_uuid=clone.album_release_uuid,
                artist_uuid=artist.artist_uuid,
            ))

        # Step 4: Clone TrackVersion links
        track_versions = original.track_versions
        for tv in track_versions:
            bridge = await self.db.execute(
                select(TrackVersionAlbumReleaseBridge).where(
                    TrackVersionAlbumReleaseBridge.track_version_uuid == tv.track_version_uuid,
                    TrackVersionAlbumReleaseBridge.album_release_uuid == original.album_release_uuid,
                )
            )
            bridge_data = bridge.scalar_one_or_none()
            self.db.add(TrackVersionAlbumReleaseBridge(
                track_version_uuid=tv.track_version_uuid,
                album_release_uuid=clone.album_release_uuid,
                track_number=bridge_data.track_number if bridge_data else None
            ))

        # Step 5: Clone Tag and Genre links
        for tag in original.tags:
            self.db.add(AlbumReleaseTagBridge(
                album_release_uuid=clone.album_release_uuid,
                tag_uuid=tag.tag_uuid,
            ))

        for genre in original.genres:
            self.db.add(AlbumReleaseGenreBridge(
                album_release_uuid=clone.album_release_uuid,
                genre_uuid=genre.genre_uuid,
            ))

        await self.db.flush()
        return clone


    async def link_release_to_collection(
            self,
            album_release_uuid: UUID,
            collection_uuid: UUID,
    ):
        # Get the release and its parent album
        result = await self.db.execute(
            select(AlbumRelease)
            .where(AlbumRelease.album_release_uuid == album_release_uuid)
            .options(selectinload(AlbumRelease.album))
        )
        album_release = result.scalars().first()
        if not album_release:
            raise ValueError("AlbumRelease not found")

        album = album_release.album
        if not album:
            raise ValueError("AlbumRelease has no parent Album")

        # Link album to collection if not already linked
        result = await self.db.execute(
            select(CollectionAlbumBridge).where(
                CollectionAlbumBridge.album_uuid == album.album_uuid,
                CollectionAlbumBridge.collection_uuid == collection_uuid,
            )
        )
        if not result.scalars().first():
            self.db.add(CollectionAlbumBridge(
                album_uuid=album.album_uuid,
                collection_uuid=collection_uuid
            ))

        # Link specific release to collection if not already linked
        result = await self.db.execute(
            select(CollectionAlbumReleaseBridge).where(
                CollectionAlbumReleaseBridge.album_release_uuid == album_release_uuid,
                CollectionAlbumReleaseBridge.collection_uuid == collection_uuid,
            )
        )
        if not result.scalars().first():
            self.db.add(CollectionAlbumReleaseBridge(
                album_release_uuid=album_release_uuid,
                collection_uuid=collection_uuid
            ))

        # Only flush, never commit inside `session.begin()`
        await self.db.flush()

    async def fetch_album_image(self, album: Album, cover_art_archive: CoverArtArchiveAPI):
        if not album.musicbrainz_release_group_id:
            return album

        resp = await cover_art_archive.get_by_release_group(album.musicbrainz_release_group_id)
        if not resp:
            return album

        for image in resp["images"]:
            if image.get("front"):
                album.image_url = image["thumbnails"].get("large") or image["thumbnails"].get("500")
                album.image_thumbnail_url = image["thumbnails"].get("small") or image["thumbnails"].get("250")
                self.db.add(album)
                await self.db.flush()
                break

        return album

    async def fetch_album_release_image(self, release: AlbumRelease, cover_art_archive: CoverArtArchiveAPI):
        if not release.musicbrainz_release_id:
            return release

        resp = await cover_art_archive.get_by_release(release.musicbrainz_release_id)
        if not resp:
            return release

        for image in resp["images"]:
            if image.get("front"):
                release.image_url = image["thumbnails"].get("large") or image["thumbnails"].get("500")
                release.image_thumbnail_url = image["thumbnails"].get("small") or image["thumbnails"].get("250")
                self.db.add(release)
                await self.db.flush()
                break

        return release

    async def gather_images(self):
        cover_art_archive = CoverArtArchiveAPI()

        result = await self.db.execute(
            select(Album).where(
                Album.image_url == None,
                Album.musicbrainz_release_group_id != None
            )
        )
        albums = result.scalars().all()

        for index, album in enumerate(albums, start=1):
            logger.info(f"Gathering images for album number {index} of {len(albums)}")
            await self.fetch_album_image(album, cover_art_archive)

        await self.db.commit()

        release_result = await self.db.execute(
            select(AlbumRelease).where(
                AlbumRelease.image_url == None,
                AlbumRelease.musicbrainz_release_id != None
            )
        )
        album_releases = release_result.scalars().all()

        for index, release in enumerate(album_releases, start=1):
            logger.info(f"Gathering images for album release number {index} of {len(album_releases)}")
            await self.fetch_album_release_image(release, cover_art_archive)

        await self.db.commit()

