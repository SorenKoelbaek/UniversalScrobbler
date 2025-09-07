from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import AlbumRead, ArtistRead, TrackRead, MusicSearchResponse, PaginatedResponse, ArtistBase
from services.music_service import MusicService
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from models.sqlmodels import User, CollectionTrack
from sqlmodel import select
from uuid import UUID
from typing import List, Optional
from fastapi.responses import FileResponse

router = APIRouter(
    prefix="/music",
    tags=["music"]
)

@router.get("/albums/{album_uuid}", response_model=AlbumRead)
async def get_album(
    album_uuid: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Fetch a single album."""
    music_service = MusicService(db)
    return await music_service.get_album(album_uuid)

@router.get("/file/{collection_track_uuid}")
async def stream_file(collection_track_uuid: UUID, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(CollectionTrack).where(CollectionTrack.collection_track_uuid == collection_track_uuid))
    ctrack = result.scalar_one_or_none()
    if not ctrack:
        raise HTTPException(404, "File not found")

    return FileResponse(ctrack.path, headers={"Accept-Ranges": "bytes"})

@router.get("/albums/", response_model=PaginatedResponse[AlbumRead])
async def get_all_albums(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = None,
    db: AsyncSession = Depends(get_async_session),
):
    """Fetch paginated albums with optional search."""
    music_service = MusicService(db)
    return await music_service.get_all_albums(offset=offset, limit=limit, search=search)


@router.get("/artists/{artist_uuid}", response_model=ArtistRead)
async def get_artist(
    artist_uuid: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Fetch a single artist."""
    music_service = MusicService(db)
    return await music_service.get_artist(artist_uuid)


@router.get("/artists/", response_model=PaginatedResponse[ArtistBase])
async def get_all_artists(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = None,
    db: AsyncSession = Depends(get_async_session),
):
    """Fetch paginated artists with optional search."""
    music_service = MusicService(db)
    return await music_service.get_all_artists(offset=offset, limit=limit, search=search)

@router.get("/tracks/{track_uuid}", response_model=TrackRead)
async def get_track(track_uuid: UUID, db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch a single track."""
    music_service = MusicService(db)
    return await music_service.get_track(track_uuid)


@router.get("/search/", response_model=MusicSearchResponse)
async def search(
        track_name: Optional[str] = None,
        artist_name: Optional[str] = None,
        album_name: Optional[str] = None,
        db: AsyncSession = Depends(get_async_session),
        user: User = Depends(get_current_user)
):
    """Search for tracks with optional parameters."""
    music_service = MusicService(db)

    if track_name is not None:
        tracks = await music_service.search_track(user.user_uuid, track_name, artist_name, album_name)
        return MusicSearchResponse(type="track", result=tracks)
    if album_name is not None:
        albums = await music_service.search_album(user.user_uuid,artist_name, album_name)
        return MusicSearchResponse(type="album", result=albums)
    if artist_name is not None:
        artists = await music_service.search_artist(artist_name)
        return MusicSearchResponse(type="artist", result=artists)
