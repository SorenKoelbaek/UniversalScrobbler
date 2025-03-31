from sqlmodel import select
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Collection, Album, AlbumRelease
from models.appmodels import CollectionRead, CollectionSimple
from uuid import UUID
from fastapi import HTTPException
from typing import List
from pydantic import parse_obj_as

class CollectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_collection(self, collection_id: UUID) -> CollectionRead:
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Collection).where(Collection.user_uuid == collection_id)
        .options(
            selectinload(Collection.albums).selectinload(Album.artists),  # Eager load albums and their artists
            selectinload(Collection.albums).selectinload(Album.tracks),  # Eager load albums and their tracks
            selectinload(Collection.album_releases).selectinload(AlbumRelease.artists)
            # Eager load album releases and their artists
        ))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionRead.model_validate(collection)  # Use model_validate instead of parse_obj

    async def get_primary_collection(self, user_uuid: UUID) -> CollectionRead:
        result = await self.db.execute(select(Collection).where(Collection.user_uuid == user_uuid)
        .options(
            selectinload(Collection.albums).selectinload(Album.artists),  # Eager load albums and their artists
            selectinload(Collection.albums).selectinload(Album.tracks),  # Eager load albums and their tracks
            selectinload(Collection.album_releases).selectinload(AlbumRelease.artists)
            # Eager load album releases and their artists
        ))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionRead.model_validate(collection)  # Use model_validate instead of parse_obj

    async def get_collection_simple(self, collection_id: UUID) -> CollectionSimple:
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Collection).where(Collection.collection_uuid == collection_id).options(selectinload(Collection.albums), selectinload(Collection.album_releases)))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionSimple.model_validate(collection)  # Use model_validate instead of parse_obj