from collections import defaultdict
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from sqlalchemy import func
from sqlmodel import select, cast
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Album, Artist, Track, Tag, Genre, AlbumTagBridge, TrackVersion, TrackVersionTagBridge, \
    ArtistTagBridge, TrackAlbumBridge, AlbumArtistBridge, SearchIndex, ScrobbleResolutionIndex, \
    ScrobbleResolutionSearchIndex
from models.appmodels import AlbumRead, ArtistRead, TrackRead, TagBase, PaginatedResponse, ArtistBase, TrackReadSimple, \
    AlbumFindSimilarRequest
from uuid import UUID
from fastapi import HTTPException
from typing import List, Optional, Set
import logging
logger = logging.getLogger(__name__)
from dependencies.musicbrainz_api import MusicBrainzAPI

import re
from rapidfuzz import fuzz
import numpy as np

musicbrainz_api = MusicBrainzAPI()

SIMILARITY_WEIGHTS = {
    "style": 0.4,
    "artist": 0.3,
    "type": 0.2,
    "year": 0.1,
}

def rank_album_preference(album, expected_title: str):
    title = (album.title or "").lower()
    expected = (expected_title or "").lower()

    # Scoring by heuristic: higher is better
    score = 0
    if title == expected:
        score += 100  # Exact match wins
    elif expected in title:
        score += 50  # Contains target

    if album.release_date:
        score += max(0, 100 - (album.release_date.year - 1960))  # Favor older

    if any(t.name == "Remix" for t in (album.types or [])):
        score -= 30
    if any(t.name == "Live" for t in (album.types or [])):
        score -= 20

    return score


class MusicService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_similar_albums(
        self,
        request: AlbumFindSimilarRequest,
        limit: int = 50
    ) -> PaginatedResponse[AlbumRead]:
        album_uuids: List[UUID] = request.albums
        if not album_uuids:
            raise ValueError("At least one album UUID must be provided")

        # Main similarity SQL: for each candidate album, get MAX score to any input album
        # Weight: style (0.4), artist (0.3), type (0.2), year (0.1), year uses Euclidean
        sql = text("""
            SELECT
                target.album_uuid,
                MAX(
                    0.4 * (1 - (target.style_vector <=> seed.style_vector)) +
                    0.3 * (1 - (target.artist_vector <=> seed.artist_vector)) +
                    0.2 * (1 - (target.type_vector <=> seed.type_vector)) +
                    0.1 * (1 / (1 + (target.year_vector <-> seed.year_vector)))
                ) AS score
            FROM album_vector AS target
            JOIN album_vector AS seed ON seed.album_uuid = ANY(:seed_ids)
            WHERE target.album_uuid != ALL(:seed_ids)
            GROUP BY target.album_uuid
            ORDER BY score DESC
            LIMIT :limit
        """)

        result = await self.db.execute(sql, {"seed_ids": album_uuids, "limit": limit * 2})
        rows = result.fetchall()

        # Extract just the UUIDs
        result_ids = [row[0] for row in rows]

        if not result_ids:
            return PaginatedResponse(total=0, offset=0, limit=limit, items=[])

        # Fetch matching albums
        stmt = (
            select(Album)
            .where(Album.album_uuid.in_(result_ids))
            .options(
                selectinload(Album.artists),
                selectinload(Album.tracks),
                selectinload(Album.tags),
                selectinload(Album.types),
                selectinload(Album.releases),
            )
        )
        result = await self.db.execute(stmt)
        albums = result.scalars().all()

        # Sort again to match score order
        album_map = {a.album_uuid: a for a in albums}
        ordered = [album_map[uuid] for uuid in result_ids if uuid in album_map][:limit]

        adapter = TypeAdapter(List[AlbumRead])
        return PaginatedResponse(
            total=len(ordered),
            offset=0,
            limit=limit,
            items=adapter.validate_python(ordered)
        )

    async def get_album(self, album_uuid: UUID) -> AlbumRead:
        """Retrieve a single album, filter canonical tracks AFTER model validation."""

        # 1. Load the album + relations
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

        # 2. Load the canonical track UUIDs and their track_numbers
        stmt_canonical_tracks = (
            select(TrackAlbumBridge.track_uuid, TrackAlbumBridge.track_number)
            .where(
                TrackAlbumBridge.album_uuid == album_uuid,
                TrackAlbumBridge.canonical_first.is_(True),
            )
        )
        result_canonical = await self.db.execute(stmt_canonical_tracks)
        canonical_rows = result_canonical.all()

        canonical_track_uuids = {row[0] for row in canonical_rows}
        track_number_map = {row[0]: row[1] for row in canonical_rows}

        # 3. Model validate first (detach!)
        album_read = AlbumRead.model_validate(album)

        # 4. Filter tracks AFTER validation
        album_read.tracks = [
            track for track in album_read.tracks
            if track.track_uuid in canonical_track_uuids
        ]

        # 5. Inject track_number into each track
        for track in album_read.tracks:
            track.track_number = track_number_map.get(track.track_uuid)

        # 6. Load and overwrite tag counts
        tag_counts_result = await self.db.execute(
            select(AlbumTagBridge.tag_uuid, AlbumTagBridge.count)
            .where(AlbumTagBridge.album_uuid == album_uuid)
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

    async def get_all_albums(
            self,
            offset: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
    ) -> PaginatedResponse[AlbumRead]:
        """Retrieve paginated albums with optional full-text search from search_index."""

        if search:
            ts_query = func.plainto_tsquery("english", search)

            # Step 1: Query the materialized view to get matching album UUIDs
            index_query = (
                select(SearchIndex.entity_uuid)
                .where(SearchIndex.entity_type == "album")
                .where(SearchIndex.search_vector.op("@@")(ts_query))
                .order_by(func.ts_rank(SearchIndex.search_vector, ts_query).desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self.db.execute(index_query)
            matching_uuids = result.scalars().all()

            if not matching_uuids:
                return PaginatedResponse(total=0, offset=offset, limit=limit, items=[])

            # Step 2: Count total matches from index (for pagination)
            count_query = (
                select(func.count())
                .select_from(SearchIndex)
                .where(SearchIndex.entity_type == "album")
                .where(SearchIndex.search_vector.op("@@")(ts_query))
            )
            total = (await self.db.execute(count_query)).scalar_one()

            # Step 3: Fetch actual album data
            album_query = (
                select(Album)
                .where(Album.album_uuid.in_(matching_uuids))
                .options(
                    selectinload(Album.artists),
                    selectinload(Album.tracks),
                    selectinload(Album.tags),
                    selectinload(Album.types),
                    selectinload(Album.releases),
                )
            )
            album_result = await self.db.execute(album_query)
            albums = album_result.scalars().all()

            # Reorder based on the order of matching UUIDs
            uuid_order = {uuid: idx for idx, uuid in enumerate(matching_uuids)}
            albums.sort(key=lambda a: uuid_order.get(a.album_uuid, len(matching_uuids)))

            album_list_adapter = TypeAdapter(list[AlbumRead])
            return PaginatedResponse(
                total=total,
                offset=offset,
                limit=limit,
                items=album_list_adapter.validate_python(albums),
            )

        else:
            # Fallback: no search, regular pagination
            query = (
                select(Album)
                .options(
                    selectinload(Album.artists),
                    selectinload(Album.tracks),
                    selectinload(Album.tags),
                    selectinload(Album.types),
                    selectinload(Album.releases),
                )
                .offset(offset)
                .limit(limit)
            )
            result = await self.db.execute(query)
            albums = result.scalars().all()

            total_result = await self.db.execute(select(func.count()).select_from(Album))
            total = total_result.scalar_one()

            album_list_adapter = TypeAdapter(list[AlbumRead])
            return PaginatedResponse(
                total=total,
                offset=offset,
                limit=limit,
                items=album_list_adapter.validate_python(albums),
            )

    async def get_artist(self, artist_uuid: UUID) -> ArtistRead:
        result = await self.db.execute(
            select(Artist)
            .where(Artist.artist_uuid == artist_uuid)
            .options(
                selectinload(Artist.albums).selectinload(Album.tracks),
                selectinload(Artist.albums).selectinload(Album.types),
                selectinload(Artist.tags),
                selectinload(Artist.album_releases)
            )
        )
        artist = result.scalar_one_or_none()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

        # Filter albums that have at least one track
        artist.albums = [album for album in artist.albums if album.tracks]

        # Get tag counts from bridge
        tag_counts_result = await self.db.execute(
            select(ArtistTagBridge.tag_uuid, ArtistTagBridge.count)
            .where(ArtistTagBridge.artist_uuid == artist_uuid)
        )
        tag_counts = dict(tag_counts_result.all())

        # Inject counts into tag models
        artist_read = ArtistRead.model_validate(artist)
        artist_read.tags = [
            TagBase(
                tag_uuid=tag.tag_uuid,
                name=tag.name,
                count=tag_counts.get(tag.tag_uuid, 0)
            )
            for tag in artist.tags
        ]

        return artist_read

    async def get_all_artists(
            self,
            offset: int = 0,
            limit: int = 100,
            search: Optional[str] = None,
    ) -> PaginatedResponse[ArtistBase]:
        """Retrieve paginated artists with optional full-text search from search_index."""

        if search:
            ts_query = func.plainto_tsquery("english", search)

            # Step 1: Get matching artist UUIDs
            index_query = (
                select(SearchIndex.entity_uuid)
                .where(SearchIndex.entity_type == "artist")
                .where(SearchIndex.search_vector.op("@@")(ts_query))
                .order_by(func.ts_rank(SearchIndex.search_vector, ts_query).desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self.db.execute(index_query)
            matching_uuids = result.scalars().all()

            if not matching_uuids:
                return PaginatedResponse(total=0, offset=offset, limit=limit, items=[])

            # Step 2: Count total matches
            count_query = (
                select(func.count())
                .select_from(SearchIndex)
                .where(SearchIndex.entity_type == "artist")
                .where(SearchIndex.search_vector.op("@@")(ts_query))
            )
            total = (await self.db.execute(count_query)).scalar_one()

            # Step 3: Load artist models
            artist_query = (
                select(Artist)
                .where(Artist.artist_uuid.in_(matching_uuids))
            )
            artist_result = await self.db.execute(artist_query)
            artists = artist_result.scalars().all()

            # Reorder based on original search index ranking
            uuid_order = {uuid: idx for idx, uuid in enumerate(matching_uuids)}
            search_lower = search.lower()
            artists.sort(key=lambda a: (
                0 if a.name.lower() == search_lower else 1,
                uuid_order.get(a.artist_uuid, len(matching_uuids))
            ))
            adapter = TypeAdapter(list[ArtistBase])
            return PaginatedResponse(
                total=total,
                offset=offset,
                limit=limit,
                items=adapter.validate_python(artists),
            )

        else:
            # No search: fallback to regular pagination
            query = (
                select(Artist)
                .offset(offset)
                .limit(limit)
            )
            result = await self.db.execute(query)
            artists = result.scalars().all()

            total_result = await self.db.execute(select(func.count()).select_from(Artist))
            total = total_result.scalar_one()

            adapter = TypeAdapter(list[ArtistBase])
            return PaginatedResponse(
                total=total,
                offset=offset,
                limit=limit,
                items=adapter.validate_python(artists),
            )
    async def get_track(self, track_uuid: UUID) -> TrackRead:
        result = await self.db.execute(
            select(Track)
            .where(Track.track_uuid == track_uuid)
            .options(
                selectinload(Track.albums).selectinload(Album.types),
                selectinload(Track.artists),
                selectinload(Track.track_versions).selectinload(TrackVersion.tags),
                selectinload(Track.track_versions).selectinload(TrackVersion.genres),
                selectinload(Track.track_versions).selectinload(TrackVersion.album_releases),
            )
        )
        track = result.scalar_one_or_none()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")

        # Fetch tag counts from the bridge
        version_uuids = [v.track_version_uuid for v in track.track_versions]
        tag_counts_result = await self.db.execute(
            select(
                TrackVersionTagBridge.track_version_uuid,
                TrackVersionTagBridge.tag_uuid,
                TrackVersionTagBridge.count,
            ).where(
                TrackVersionTagBridge.track_version_uuid.in_(version_uuids)
            )
        )

        # Map tag counts per version
        version_tag_counts = defaultdict(dict)
        for version_uuid, tag_uuid, count in tag_counts_result.all():
            version_tag_counts[version_uuid][tag_uuid] = count

        # Convert ORM to Pydantic
        track_read = TrackRead.model_validate(track)

        # Enrich tags for each version
        for version in track_read.track_versions:
            enriched_tags = []
            for tag in version.tags:
                enriched_tags.append(TagBase(
                    tag_uuid=tag.tag_uuid,
                    name=tag.name,
                    count=version_tag_counts[version.track_version_uuid].get(tag.tag_uuid, 0)
                ))
            version.tags = enriched_tags

        return track_read

    async def get_all_tracks(self) -> List[TrackRead]:
        """Retrieve all tracks from the database."""
        result = await self.db.execute(select(Track)
        .options(
            selectinload(Track.albums).selectinload(Album.artists)))
        result = result.scalars().all()
        tract_list_adapter = TypeAdapter(list[TrackRead])
        return tract_list_adapter.validate_python(result)

    def clean_search_input(self, s: str) -> str:
        if not s:
            return ""

        s = s.lower()

        # Remove certain words commonly added to versions
        s = re.sub(
            r'\b(remaster(ed)?|remix|deluxe|expanded|anniversary|special|edition|mono|stereo|live|version|explicit)\b',
            '',
            s
        )

        # Remove anything inside parentheses
        s = re.sub(r'\(.*?\)', '', s)

        # Remove standalone 4-digit years like 1999, 2008
        s = re.sub(r'\b(19|20)\d{2}\b', '', s)

        # Collapse multiple spaces into one
        s = re.sub(r'\s+', ' ', s)

        return s.strip()

    async def search_track(
            self,
            user_uuid: UUID,
            track_name: str,
            artist_name: Optional[str] = None,
            album_name: Optional[str] = None,
            prefer_album_uuid: Optional[UUID] = None,
    ) -> List[TrackReadSimple]:
        # Build tsquery objects

        track_name = self.clean_search_input(track_name)
        if artist_name:
            artist_name = self.clean_search_input(artist_name)
        if album_name:
            album_name = self.clean_search_input(album_name)

        track_query = func.websearch_to_tsquery('simple', track_name)
        artist_query = func.websearch_to_tsquery('simple', artist_name) if artist_name else None
        album_query = func.websearch_to_tsquery('simple', album_name) if album_name else None
        limit: int = 5
        # Define weighted score
        weighted_rank = (
                1.0 * func.ts_rank(ScrobbleResolutionSearchIndex.track_name_vector, track_query) +
                (0.8 * func.ts_rank(ScrobbleResolutionSearchIndex.artist_name_vector,
                                    artist_query) if artist_name else 0) +
                (0.6 * func.ts_rank(ScrobbleResolutionSearchIndex.album_title_vector, album_query) if album_name else 0)
        )

        # Build search attempts
        search_attempts = []

        # Strict: track + artist + album
        if artist_name and album_name:
            search_attempts.append(
                select(
                    ScrobbleResolutionSearchIndex.track_uuid,
                    weighted_rank.label("score")
                )
                .where(
                    ScrobbleResolutionSearchIndex.track_name_vector.op("@@")(track_query) &
                    ScrobbleResolutionSearchIndex.artist_name_vector.op("@@")(artist_query) &
                    ScrobbleResolutionSearchIndex.album_title_vector.op("@@")(album_query)
                )
                .order_by(text("score DESC"))
                .limit(limit)
            )

        # Relaxed: track + artist
        if artist_name:
            search_attempts.append(
                select(
                    ScrobbleResolutionSearchIndex.track_uuid,
                    weighted_rank.label("score")
                )
                .where(
                    ScrobbleResolutionSearchIndex.track_name_vector.op("@@")(track_query) &
                    ScrobbleResolutionSearchIndex.artist_name_vector.op("@@")(artist_query)
                )
                .order_by(text("score DESC"))
                .limit(limit)
            )

        # More relaxed: track only
        search_attempts.append(
            select(
                ScrobbleResolutionSearchIndex.track_uuid,
                weighted_rank.label("score")
            )
            .where(
                ScrobbleResolutionSearchIndex.track_name_vector.op("@@")(track_query)
            )
            .order_by(text("score DESC"))
            .limit(limit)
        )

        # Try each query until matches
        matches = []
        for stmt in search_attempts:
            result = await self.db.exec(stmt)
            matches = result.all()
            if matches:
                break  # Stop at first successful match

        if not matches:
            return []

        # Fetch full Track models
        track_uuids = [match.track_uuid for match in matches]

        track_stmt = (
            select(Track)
            .where(Track.track_uuid.in_(track_uuids))
            .options(
                selectinload(Track.artists),
                selectinload(Track.albums).selectinload(Album.types),
            )
        )
        track_result = await self.db.exec(track_stmt)
        tracks = track_result.all()

        # Map to match order
        uuid_to_track = {track.track_uuid: track for track in tracks}
        ordered_tracks = [uuid_to_track[uuid] for uuid in track_uuids if uuid in uuid_to_track]

        # Sort albums by album name similarity
        if album_name:
            for track in ordered_tracks:
                track.albums.sort(
                    key=lambda album: fuzz.token_sort_ratio(album.title.lower(), album_name.lower()),
                    reverse=True
                )
                if track.albums:
                    track.albums = [track.albums[0]]  # <- only keep the best match

        # Validate to Pydantic models
        track_list_adapter = TypeAdapter(List[TrackReadSimple])
        validated_tracks = track_list_adapter.validate_python(ordered_tracks)

        return validated_tracks[:1]  # Return a list of 1 (or 0 if no match)

    def normalize(self, name: str) -> str:
        # Replace all dash variants with a plain hyphen, lowercase, strip whitespace
        return re.sub(r"[-‐‑‒–—―]", "-", name.strip().lower())

    async def search_album(
            self,
            user_uuid: UUID,
            artist_name: Optional[str] = None,
            album_name: Optional[str] = None
    ):
        if not album_name:
            return []

        raw_query = f"{album_name or ''} {artist_name or ''}"
        ts_query = func.plainto_tsquery("english", raw_query)

        match_query = (
            select(ScrobbleResolutionIndex.album_uuid)
            .where(ScrobbleResolutionIndex.search_vector.op("@@")(ts_query))
            .order_by(func.ts_rank(ScrobbleResolutionIndex.search_vector, ts_query).desc())
            .limit(1)
        )

        result = await self.db.execute(match_query)
        match = result.scalar_one_or_none()

        if not match:
            return []

        album_query = (
            select(Album)
            .where(Album.album_uuid == match)
            .options(
                selectinload(Album.artists),
                selectinload(Album.tracks),
                selectinload(Album.tags),
                selectinload(Album.types),
                selectinload(Album.releases),
            )
        )
        result = await self.db.execute(album_query)
        album = result.scalar_one_or_none()

        if not album:
            return []

        adapter = TypeAdapter(List[AlbumRead])
        return adapter.validate_python([album])

    async def search_artist(
            self,
            artist_name: Optional[str] = None,
    ):
        # Start with the basic query to select tracks
        query = select(Artist).options(selectinload(Artist.albums),selectinload(Artist.album_releases))

        if artist_name:
            query = query.where(Artist.name.ilike(f"%{artist_name}%"))

        # Execute the query
        result = await self.db.execute(query)
        artists = result.scalars().all()
        # Optionally return a simpler response with TrackRead
        track_list_adapter = TypeAdapter(list[ArtistRead])
        return track_list_adapter.validate_python(artists)