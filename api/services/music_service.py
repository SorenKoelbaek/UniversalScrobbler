from sqlmodel import select, or_
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Album, Artist, Track
from models.appmodels import AlbumRead, ArtistRead, TrackRead
from uuid import UUID
from fastapi import HTTPException
from typing import List, Optional
from config import settings
import logging
logger = logging.getLogger(__name__)
from services.discogs_service import DiscogsService


discogs_service = DiscogsService()


class MusicService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_album(self, album_uuid: UUID) -> AlbumRead:
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Album).where(Album.album_uuid == album_uuid).options(selectinload(Album.artists), selectinload(Album.tracks)))
        album = result.scalar_one_or_none()
        if not album:
            raise HTTPException(status_code=404, detail="Album not found")
        return AlbumRead.model_validate(album)  # Use model_validate instead of parse_obj

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
            selectinload(Track.albums).selectinload(Album.artists)))
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
        # Start with the basic query to select tracks
        query = select(Track).options(selectinload(Track.albums).selectinload(Album.artists))

        # Apply filters if parameters are provided (add them to the query, not overwrite)
        if track_name:
            query = query.where(Track.name.ilike(f"%{track_name}%"))

        if artist_name:
            query = query.where(Artist.name.ilike(f"%{artist_name}%"))

        if album_name:
            query = query.where(Album.title.ilike(f"%{album_name}%"))

        # Execute the query
        result = await self.db.execute(query)
        tracks = result.scalars().all()
        if not tracks:
            new_tracks = await discogs_service.get_track_from_discogs(user_uuid, self.db, artist_name,album_name, track_name)
            tracks = [new_tracks]
        # Optionally return a simpler response with TrackRead
        track_list_adapter = TypeAdapter(list[TrackRead])
        return track_list_adapter.validate_python(tracks)

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


        # Execute the query
        result = await self.db.execute(query)
        albums = result.scalars().all()
        if not albums:
            new_albums = await discogs_service.get_album_from_discogs(user_uuid, self.db, artist_name, album_name)
            albums = [new_albums]
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