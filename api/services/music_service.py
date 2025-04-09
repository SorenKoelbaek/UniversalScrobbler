from sqlmodel import select, or_
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Album, Artist, Track, Tag, Genre, AlbumTagBridge
from models.appmodels import AlbumRead, ArtistRead, TrackRead, TagBase
from uuid import UUID
from fastapi import HTTPException
from typing import List, Optional
import logging
logger = logging.getLogger(__name__)
from dependencies.musicbrainz_api import MusicBrainzAPI
from services.musicbrainz_service import MusicBrainzService
import re
from rapidfuzz import fuzz


musicbrainz_api = MusicBrainzAPI()


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
                                                ,selectinload(Album.genres)
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

        # Build the AlbumRead model and inject the tag counts
        album_read = AlbumRead.model_validate(album)
        album_read.tags = [
            TagBase(
                tag_uuid=tag.tag_uuid,
                name=tag.name,
                count=tag_counts.get(tag.tag_uuid, 0),
            )
            for tag in album.tags
        ]

        return album_read

    async def get_all_albums(self) -> List[AlbumRead]:
        """Retrieve all albums from the database."""
        # Fetch albums along with their artists and tracks
        result = await self.db.execute(
            select(Album)
            .options(
                selectinload(Album.artists),
                selectinload(Album.tracks)
            )  # Ensure related fields are loaded
        )

        albums = result.scalars().all()

        album_list_adapter = TypeAdapter(list[AlbumRead])
        return album_list_adapter.validate_python(albums)

    async def get_artist(self, artist_uuid: UUID) -> ArtistRead:
        """Retrieve a single artist based on UUID."""
        result = await self.db.execute(select(Artist).where(Artist.artist_uuid == artist_uuid).options(selectinload(Artist.albums), selectinload(Artist.album_releases)))
        artist = result.scalar_one_or_none()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")
        return ArtistRead.model_validate(artist)  # Use model_validate instead of parse_obj

    async def get_all_artists(self) -> List[ArtistRead]:
        """Retrieve all artists from the database."""
        result = await self.db.execute(select(Artist).options(selectinload(Artist.albums)))
        artists = result.scalars().all()

        artist_list_adapter = TypeAdapter(list[ArtistRead])
        return artist_list_adapter.validate_python(artists)

        return [ArtistRead.model_validate(artist) for artist in artists]  # Use model_validate instead of parse_obj

    async def get_track(self, track_uuid: UUID) -> TrackRead:
        """Retrieve a single track based on UUID."""
        result = await self.db.execute(select(Track).where(Track.track_uuid == track_uuid)
                                       .options(
            selectinload(Track.albums),selectinload(Track.artists)))
        track = result.scalar_one_or_none()
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        return TrackRead.model_validate(track)  # Use model_validate instead of parse_obj

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

    ):

        query = (
            select(Track)
            .join(Track.artists)
            .join(Track.albums)
            .options(
                selectinload(Track.artists),
                selectinload(Track.albums)
            )
        )

        if track_name:
            query = query.where(Track.name.ilike(f"%{track_name}%"))

        if artist_name:
            query = query.where(Artist.name.ilike(f"%{artist_name}%"))

        if album_name:
            query = query.where(Album.title.ilike(f"%{album_name}%"))

        result = await self.db.execute(query)
        tracks = result.scalars().all()

        if not tracks:
            musicbrainz_service = MusicBrainzService(self.db, musicbrainz_api)
            release_group_id = await musicbrainz_api.search_recording_and_return_release_id(track_name, artist_name, album_name)
            if not release_group_id:
                release_group_id = await musicbrainz_api.search_recording_and_return_release_id(track_name, artist_name)
            if release_group_id:
                album, album_release = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(release_group_id, True)
                await self.db.commit()
                query = select(Track).options(
                    selectinload(Track.albums),
                            selectinload(Track.artists)
                            ).where(Track.albums.any(Album.album_uuid == album.album_uuid))
                result = await self.db.execute(query)
                tracks = result.scalars().all()
                if track_name:
                    normalized_track_name = track_name.strip().lower()
                    matching_tracks = [
                        t for t in tracks
                        if t.name and self.normalize(t.name) in normalized_track_name
                    ]
                    # If nothing found, try fuzzy match
                    threshold = 85  # adjust for strictness
                    if not matching_tracks:
                        matching_tracks = [
                            t for t in tracks
                            if t.name and fuzz.partial_ratio(self.normalize(t.name), normalized_track_name) >= threshold
                        ]
                if not matching_tracks:
                    logger.info(f"🤷 No match for '{track_name}' in album '{album.title}'")
                else:
                    tracks = matching_tracks

        if not tracks:
            return None
        track_list_adapter = TypeAdapter(list[TrackRead])
        return track_list_adapter.validate_python(tracks)


    def normalize(self, name: str) -> str:
        # Replace all dash variants with a plain hyphen, lowercase, strip whitespace
        return re.sub(r"[-‐‑‒–—―]", "-", name.strip().lower())

    async def search_album(
            self,
            user_uuid: UUID,
            artist_name: Optional[str] = None,
            album_name: Optional[str] = None
    ):
        # Start with the basic query to select tracks
        query = select(Album).options(selectinload(Album.artists),selectinload(Album.tracks))

        if album_name:
            query = query.where(Album.title.ilike(f"%{album_name}%"))
        # Apply filters if parameters are provided (add them to the query, not overwrite)
        if artist_name:
            query = query.where(Artist.name.ilike(f"%{artist_name}%"))

        result = await self.db.execute(query)
        albums = result.scalars().all()
        if not albums:
            musicbrainz_service = MusicBrainzService(self.db, musicbrainz_api)
            release_id = await musicbrainz_api.get_first_release_id_by_artist_and_album(artist_name, album_name)
            if release_id:
                album, album_release = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(release_id, True)
                albums = [album]
        # Optionally return a simpler response with TrackRead
        track_list_adapter = TypeAdapter(list[AlbumRead])
        return track_list_adapter.validate_python(albums)

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