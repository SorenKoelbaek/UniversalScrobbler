from collections import defaultdict
from sqlalchemy import text, func
from sqlmodel import select
from pydantic import TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import (
    Album,
    Artist,
    Track,
    AlbumTagBridge,
    TrackVersion,
    ArtistTagBridge,
    TrackAlbumBridge,
    SearchIndex,
    LibraryTrack,
    TrackVersionAlbumReleaseBridge
)
from models.appmodels import (
    AlbumRead,
    ArtistRead,
    TrackRead,
    TagBase,
    TrackReadSimple,
)
from uuid import UUID
from fastapi import HTTPException
from typing import List, Optional
import logging
import re
from dependencies.musicbrainz_api import MusicBrainzAPI
from services.musicbrainz_service import MusicBrainzService
musicbrainz_api = MusicBrainzAPI()

logger = logging.getLogger(__name__)

def normalize_track_number(raw: str) -> Optional[int]:
    """
    Convert vinyl-style track numbers like 'A1', 'C5', 'D12'
    into a continuous integer position.

    Rules:
    - Side letters (A=0, B=1, ...) are converted to offsets of 100.
    - Numbers are parsed after the letter.
    - Plain numbers ("7", "12") are kept as-is.
    """
    if not raw:
        return None

    # Match like A1, B12, etc.
    match = re.match(r"^([A-Z])(\d+)$", raw.strip(), re.I)
    if match:
        side = match.group(1).upper()
        track_no = int(match.group(2))
        side_index = ord(side) - ord("A")
        return side_index * 100 + track_no

    # Pure number
    if raw.isdigit():
        return int(raw)

    # Fallback: can't parse
    return None

class MusicService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------------------
    # 🎵 Core album/artist/track queries
    # -------------------------------------------------------------------------

    async def get_album(self, album_uuid: UUID, should_hydrate: bool = False) -> AlbumRead:
        stmt_album = (
            select(Album)
            .options(
                selectinload(Album.tracks),
                selectinload(Album.artists),
                selectinload(Album.tags),
                selectinload(Album.types),
                selectinload(Album.releases),
            )
            .where(Album.album_uuid == album_uuid)
        )
        result_album = await self.db.execute(stmt_album)
        album = result_album.scalar_one_or_none()

        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
        logger.info(album)
        # 🔹 Auto-populate if shallow (no releases/tracks but has release_group_id)
        if not album.releases and not album.tracks and album.musicbrainz_release_group_id and should_hydrate:
            logger.info(f"Hydrating shallow album {album.title} ({album.musicbrainz_release_group_id})")
            mb_service = MusicBrainzService(self.db, musicbrainz_api)
            try:
                await mb_service.add_release_tracks_to_shallow_album(album)

                refreshed = await self.db.execute(
                    select(Album)
                    .execution_options(populate_existing=True)  # 👈 forces overwrite
                    .options(
                        selectinload(Album.tracks),
                        selectinload(Album.artists),
                        selectinload(Album.tags),
                        selectinload(Album.types),
                        selectinload(Album.releases),
                    )
                    .where(Album.album_uuid == album.album_uuid)
                )
                album = refreshed.scalar_one()
            except Exception as e:
                logger.warning(f"⚠️ Failed to hydrate album {album.title}: {e}")

        album_read = AlbumRead.model_validate(album)

        # 🔗 Enrich tracks with library + track_number info
        track_ids = [t.track_uuid for t in album_read.tracks]
        if track_ids:
            # --- Step 1: TrackVersion mapping ---
            result_versions = await self.db.execute(
                select(TrackVersion.track_uuid, TrackVersion.track_version_uuid)
                .where(TrackVersion.track_uuid.in_(track_ids))
            )
            version_map = {}
            version_ids = []
            for track_uuid, track_version_uuid in result_versions.all():
                version_map.setdefault(track_uuid, []).append(track_version_uuid)
                version_ids.append(track_version_uuid)

            # --- Step 2: LibraryTrack mapping ---
            lib_map = {}
            if version_ids:
                result_lib = await self.db.execute(
                    select(LibraryTrack.track_version_uuid, LibraryTrack.library_track_uuid)
                    .where(LibraryTrack.track_version_uuid.in_(version_ids))
                )
                lib_map = dict(result_lib.all())

            # --- Step 3: Track numbers from TrackVersionAlbumReleaseBridge ---
            release_ids = [r.album_release_uuid for r in album_read.releases]
            tv_number_map = {}
            if version_ids and release_ids:
                result_numbers = await self.db.execute(
                    select(
                        TrackVersionAlbumReleaseBridge.track_version_uuid,
                        TrackVersionAlbumReleaseBridge.album_release_uuid,
                        TrackVersionAlbumReleaseBridge.track_number,
                    ).where(
                        TrackVersionAlbumReleaseBridge.track_version_uuid.in_(version_ids),
                        TrackVersionAlbumReleaseBridge.album_release_uuid.in_(release_ids),
                    )
                )
                for row in result_numbers.all():
                    tv_number_map[(row.track_version_uuid, row.album_release_uuid)] = row.track_number

            # --- Step 4: Fallback track numbers from TrackAlbumBridge ---
            result_album_numbers = await self.db.execute(
                select(
                    TrackAlbumBridge.track_uuid,
                    TrackAlbumBridge.album_uuid,
                    TrackAlbumBridge.track_number,
                ).where(
                    TrackAlbumBridge.track_uuid.in_(track_ids),
                    TrackAlbumBridge.album_uuid == album_uuid,
                )
            )
            ta_number_map = {(row.track_uuid, row.album_uuid): row.track_number for row in result_album_numbers.all()}

            # --- Step 5: Apply enrichments ---
            for track in album_read.tracks:
                # Inject library info
                versions = version_map.get(track.track_uuid, [])
                for v in versions:
                    if v in lib_map:
                        track.library_track_uuid = lib_map[v]
                        has_digital = True
                        break  # first playable version wins

                # Inject track number (prefer TrackVersionAlbumReleaseBridge, else TrackAlbumBridge)
                track_number = None
                for v in versions:
                    for rel in release_ids:
                        key = (v, rel)
                        if key in tv_number_map and tv_number_map[key] is not None:
                            track_number = tv_number_map[key]
                            break
                    if track_number:
                        break
                if not track_number:
                    track_number = ta_number_map.get((track.track_uuid, album_uuid))
                track.track_number = track_number
                if track.track_number:
                    track.track_position = normalize_track_number(track.track_number)

        # 🎯 Tag counts
        tag_counts_result = await self.db.execute(
            select(AlbumTagBridge.tag_uuid, AlbumTagBridge.count).where(
                AlbumTagBridge.album_uuid == album_uuid
            )
        )
        tag_counts = dict(tag_counts_result.all())
        album_read.tags = [
            TagBase(
                tag_uuid=tag.tag_uuid,
                name=tag.name,
                count=tag_counts.get(tag.tag_uuid, 0),
            )
            for tag in album_read.tags
        ]

        return album_read

    async def get_artist(self, artist_uuid: UUID) -> ArtistRead:
        result = await self.db.execute(
            select(Artist)
            .where(Artist.artist_uuid == artist_uuid)
            .options(
                selectinload(Artist.albums).selectinload(Album.tracks),
                selectinload(Artist.albums).selectinload(Album.types),
                selectinload(Artist.tags),
                selectinload(Artist.album_releases),
            )
        )
        artist = result.scalar_one_or_none()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

        tag_counts_result = await self.db.execute(
            select(ArtistTagBridge.tag_uuid, ArtistTagBridge.count).where(
                ArtistTagBridge.artist_uuid == artist_uuid
            )
        )
        tag_counts = dict(tag_counts_result.all())

        artist_read = ArtistRead.model_validate(artist)
        artist_read.tags = [
            TagBase(
                tag_uuid=tag.tag_uuid,
                name=tag.name,
                count=tag_counts.get(tag.tag_uuid, 0),
            )
            for tag in artist.tags
        ]
        return artist_read

    async def get_track(self, track_uuid: UUID) -> TrackRead:
        result = await self.db.execute(
            select(Track)
            .where(Track.track_uuid == track_uuid)
            .options(
                selectinload(Track.albums).selectinload(Album.types),
                selectinload(Track.artists),
                selectinload(Track.track_versions).selectinload(TrackVersion.tags),
                selectinload(Track.track_versions).selectinload(TrackVersion.genres),
                selectinload(Track.track_versions).selectinload(
                    TrackVersion.album_releases
                ),
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        track_read = TrackRead.model_validate(track)

        # --- Step 1: Collect track_version ids
        version_ids = [v.track_version_uuid for v in track.track_versions]

        # --- Step 2: Library mapping
        lib_map = {}
        if version_ids:
            lib_result = await self.db.execute(
                select(
                    LibraryTrack.track_version_uuid,
                    LibraryTrack.library_track_uuid,
                ).where(LibraryTrack.track_version_uuid.in_(version_ids))
            )
            lib_map = dict(lib_result.all())

        # --- Step 3: Track numbers from TrackVersionAlbumReleaseBridge
        release_ids = [r.album_release_uuid for v in track.track_versions for r in v.album_releases]
        tv_number_map = {}
        if version_ids and release_ids:
            result_numbers = await self.db.execute(
                select(
                    TrackVersionAlbumReleaseBridge.track_version_uuid,
                    TrackVersionAlbumReleaseBridge.album_release_uuid,
                    TrackVersionAlbumReleaseBridge.track_number,
                ).where(
                    TrackVersionAlbumReleaseBridge.track_version_uuid.in_(version_ids),
                    TrackVersionAlbumReleaseBridge.album_release_uuid.in_(release_ids),
                )
            )
            for row in result_numbers.all():
                tv_number_map[(row.track_version_uuid, row.album_release_uuid)] = row.track_number

        # --- Step 4: Fallback numbers from TrackAlbumBridge
        result_album_numbers = await self.db.execute(
            select(
                TrackAlbumBridge.track_uuid,
                TrackAlbumBridge.album_uuid,
                TrackAlbumBridge.track_number,
            ).where(TrackAlbumBridge.track_uuid == track_uuid)
        )
        ta_number_map = {(row.track_uuid, row.album_uuid): row.track_number for row in result_album_numbers.all()}

        # --- Step 5: Apply enrichments to TrackRead
        for version in track_read.track_versions:
            # Inject library info
            if version.track_version_uuid in lib_map:
                track_read.library_track_uuid = lib_map[version.track_version_uuid]
                has_digital = True
                break

        # Inject track_number + track_position
        track_number = None
        for version in track_read.track_versions:
            for rel in version.album_releases:
                key = (version.track_version_uuid, rel.album_release_uuid)
                if key in tv_number_map and tv_number_map[key] is not None:
                    track_number = tv_number_map[key]
                    break
            if track_number:
                break
        if not track_number and track.albums:
            for album in track.albums:
                key = (track.track_uuid, album.album_uuid)
                if key in ta_number_map and ta_number_map[key] is not None:
                    track_number = ta_number_map[key]
                    break

        track_read.track_number = track_number
        if track_number:
            track_read.track_position = normalize_track_number(track_number)

        return track_read


    # -------------------------------------------------------------------------
    # 🔍 Basic search unified now
    # -------------------------------------------------------------------------
    async def search(self, query: str, limit: int = 25, only_digital: bool = True) -> dict:
        # --- Albums ---
        albums_result = await self.db.execute(
            select(Album)
            .where(Album.title.ilike(f"%{query}%"))
            .limit(limit)
            .options(
                selectinload(Album.artists),
                selectinload(Album.tracks),
                selectinload(Album.types),
                selectinload(Album.releases),
                selectinload(Album.tags),
            )
        )
        albums_raw = albums_result.scalars().all()

        # --- Artists ---
        artists_result = await self.db.execute(
            select(Artist)
            .where(Artist.name.ilike(f"%{query}%"))
            .limit(limit)
            .options(
                selectinload(Artist.albums).selectinload(Album.tracks),
                selectinload(Artist.albums).selectinload(Album.types),
                selectinload(Artist.album_releases),
                selectinload(Artist.tags),
            )
        )
        artists_raw = artists_result.scalars().all()

        # --- Tracks ---
        tracks_result = await self.db.execute(
            select(Track)
            .where(Track.name.ilike(f"%{query}%"))
            .limit(limit)
            .options(
                selectinload(Track.albums).selectinload(Album.types),
                selectinload(Track.albums).selectinload(Album.artists),
                selectinload(Track.albums).selectinload(Album.releases),
                selectinload(Track.artists),
            )
        )
        tracks_raw = tracks_result.scalars().all()

        # --- Bulk digital checks ---
        album_ids = [a.album_uuid for a in albums_raw]
        track_ids = [t.track_uuid for t in tracks_raw] + [
            tr.track_uuid for a in albums_raw for tr in a.tracks
        ]

        has_digital_album = set()
        has_digital_track = set()

        if album_ids:
            result = await self.db.execute(
                select(TrackAlbumBridge.album_uuid)
                .join(TrackVersion, TrackVersion.track_uuid == TrackAlbumBridge.track_uuid)
                .join(LibraryTrack, LibraryTrack.track_version_uuid == TrackVersion.track_version_uuid)
                .where(TrackAlbumBridge.album_uuid.in_(album_ids))
            )
            has_digital_album = {row[0] for row in result.all()}

        if track_ids:
            result = await self.db.execute(
                select(Track.track_uuid)
                .join(TrackVersion, TrackVersion.track_uuid == Track.track_uuid)
                .join(LibraryTrack, LibraryTrack.track_version_uuid == TrackVersion.track_version_uuid)
                .where(Track.track_uuid.in_(track_ids))
            )
            has_digital_track = {row[0] for row in result.all()}

        # --- Now build Pydantic models with annotations ---
        albums = []
        for a in albums_raw:
            album_model = AlbumRead.model_validate(a)
            album_model.has_digital = a.album_uuid in has_digital_album
            for t in album_model.tracks:
                t.has_digital = t.track_uuid in has_digital_track
            albums.append(album_model)

        tracks = []
        for t in tracks_raw:
            track_model = TrackReadSimple.model_validate(t)
            track_model.has_digital = t.track_uuid in has_digital_track
            tracks.append(track_model)

        artists = []
        for ar in artists_raw:
            artist_model = ArtistRead.model_validate(ar)
            if only_digital:
                artist_model.albums = [
                    a for a in artist_model.albums if a.album_uuid in has_digital_album
                ]
            artists.append(artist_model)

        # --- Apply only_digital filter ---
        if only_digital:
            albums = [a for a in albums if a.has_digital]
            tracks = [t for t in tracks if t.has_digital]

        return {
            "albums": albums,
            "artists": artists,
            "tracks": tracks,
        }




