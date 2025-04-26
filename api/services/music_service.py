from collections import defaultdict

from redis.commands.search import Search
from sqlalchemy import func
from sqlmodel import select, or_, exists
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Album, Artist, Track, Tag, Genre, AlbumTagBridge, TrackVersion, TrackVersionTagBridge, \
    ArtistTagBridge, TrackAlbumBridge, AlbumArtistBridge, SearchIndex, ScrobbleResolutionIndex
from models.appmodels import AlbumRead, ArtistRead, TrackRead, TagBase, PaginatedResponse, ArtistBase, TrackReadSimple
from uuid import UUID
from fastapi import HTTPException
from typing import List, Optional
import logging
logger = logging.getLogger(__name__)
from dependencies.musicbrainz_api import MusicBrainzAPI
from services.musicbrainz_service import MusicBrainzService
import re
from rapidfuzz import fuzz
from datetime import datetime

musicbrainz_api = MusicBrainzAPI()


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

    async def get_album(self, album_uuid: UUID) -> AlbumRead:
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Album)
                                       .where(Album.album_uuid == album_uuid)
                                       .options(selectinload(Album.artists),
                                                selectinload(Album.tracks)
                                                ,selectinload(Album.tags)
                                                ,selectinload(Album.types)
                                                ,selectinload(Album.releases)))
        album = result.scalar_one_or_none()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
            # Preload tag counts from bridge
        tag_counts_result = await self.db.execute(
            select(AlbumTagBridge.tag_uuid, AlbumTagBridge.count)
            .where(AlbumTagBridge.album_uuid == album_uuid)
        )
        tag_counts = dict(tag_counts_result.all())

        # Fetch track_number per track in the album
        track_numbers_result = await self.db.execute(
            select(TrackAlbumBridge.track_uuid, TrackAlbumBridge.track_number)
            .where(TrackAlbumBridge.album_uuid == album_uuid)
        )
        track_number_map = dict(track_numbers_result.all())

        # Build AlbumRead with tag counts and track_number injected
        album_read = AlbumRead.model_validate(album)
        album_read.tags = [
            TagBase(
                tag_uuid=tag.tag_uuid,
                name=tag.name,
                count=tag_counts.get(tag.tag_uuid, 0),
            )
            for tag in album.tags
        ]
        for track in album_read.tracks:
            track.track_number = track_number_map.get(track.track_uuid)

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

    async def search_track(
            self,
            user_uuid: UUID,
            track_name: Optional[str] = None,
            artist_name: Optional[str] = None,
            album_name: Optional[str] = None,
            prefer_album_uuid: Optional[UUID] = None,  # ✅ New optional argument
    ):
        if not track_name:
            return None

        raw_query = f"{track_name or ''} {artist_name or ''} {album_name or ''}"
        logger.info(f"Raw query: {raw_query}")
        ts_query = func.plainto_tsquery("english", raw_query)

        match_query = (
            select(ScrobbleResolutionIndex)
            .where(ScrobbleResolutionIndex.search_vector.op("@@")(ts_query))
            .order_by(func.ts_rank(ScrobbleResolutionIndex.search_vector, ts_query).desc())
            .limit(1)
        )
        result = await self.db.execute(match_query)
        match = result.scalar_one_or_none()

        if not match:
            def clean_search_input(s: str) -> str:
                import re
                s = s.lower()
                s = re.sub(r'\b(remaster(ed)?|remix|version|live|mono|stereo|concept)\b', '', s)
                s = re.sub(r'\b(19|20)\d{2}\b', '', s)  # remove standalone years
                s = re.sub(r'\s+', ' ', s)
                return s.strip()

            fallback_query = clean_search_input(raw_query)
            logger.info(f"Cleaned query: {fallback_query}")
            ts_query_clean = func.plainto_tsquery("english", fallback_query)

            fallback_match_query = (
                select(ScrobbleResolutionIndex)
                .where(ScrobbleResolutionIndex.search_vector.op("@@")(ts_query_clean))
                .order_by(func.ts_rank(ScrobbleResolutionIndex.search_vector, ts_query_clean).desc())
                .limit(1)
            )

            result = await self.db.execute(fallback_match_query)
            match = result.scalar_one_or_none()

            if not match:
                logger.warning("Fallback fulltext query returned no match.")
                return None

        track_query = (
            select(Track)
            .where(Track.track_uuid == match.track_uuid)
            .options(
                selectinload(Track.artists),
                selectinload(Track.albums).selectinload(Album.types)
            )
        )
        result = await self.db.execute(track_query)
        track = result.scalar_one_or_none()

        if not track:
            return None

        track.artists = [a for a in track.artists if a.artist_uuid == match.artist_uuid]

        if prefer_album_uuid:
            preferred_album = next((a for a in track.albums if a.album_uuid == prefer_album_uuid), None)
            if preferred_album:
                track.albums = [preferred_album]
            elif album_name and track.albums:
                sorted_albums = sorted(
                    track.albums,
                    key=lambda a: rank_album_preference(a, album_name),
                    reverse=True
                )
                track.albums = [sorted_albums[0]]
            else:
                track.albums = [a for a in track.albums if a.album_uuid == match.album_uuid]
        elif album_name and track.albums:
            sorted_albums = sorted(
                track.albums,
                key=lambda a: rank_album_preference(a, album_name),
                reverse=True
            )
            track.albums = [sorted_albums[0]]
        else:
            track.albums = [a for a in track.albums if a.album_uuid == match.album_uuid]

        track_list_adapter = TypeAdapter(List[TrackReadSimple])
        return track_list_adapter.validate_python([track])

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