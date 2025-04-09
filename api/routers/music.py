from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import AlbumRead, ArtistRead, TrackRead, MusicSearchResponse
from services.music_service import MusicService
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from models.sqlmodels import User
from uuid import UUID
from typing import List, Optional

router = APIRouter(
    prefix="/music",
    tags=["music"]
)

@router.get("/albums/{album_uuid}", response_model=AlbumRead)
async def get_album(album_uuid: UUID, db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch a single album."""
    music_service = MusicService(db)
    return await music_service.get_album(album_uuid)

@router.get("/albums/", response_model=List[AlbumRead])
async def get_all_albums(db: AsyncSession = Depends(get_async_session)):
    """Fetch all albums."""
    music_service = MusicService(db)
    return await music_service.get_all_albums()

@router.get("/artists/{artist_uuid}", response_model=ArtistRead)
async def get_artist(artist_uuid: UUID, db: AsyncSession = Depends(get_async_session),user: User = Depends(get_current_user)):
    """Fetch a single artist."""
    music_service = MusicService(db)
    return await music_service.get_artist(artist_uuid)

@router.get("/artists/", response_model=List[ArtistRead])
async def get_all_artists(db: AsyncSession = Depends(get_async_session)):
    """Fetch all artists."""
    music_service = MusicService(db)
    return await music_service.get_all_artists()

@router.get("/tracks/{track_uuid}", response_model=TrackRead)
async def get_track(track_uuid: UUID, db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch a single track."""
    music_service = MusicService(db)
    return await music_service.get_track(track_uuid)

@router.get("/tracks/", response_model=List[TrackRead])
async def get_all_tracks(db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch all tracks."""
    music_service = MusicService(db)
    return await music_service.get_all_tracks()


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
