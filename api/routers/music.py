from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import AlbumRead, ArtistRead, TrackRead, MusicSearchResponse, RecommendedArtist
from services.music_service import MusicService
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from models.sqlmodels import User, LibraryTrack
from sqlmodel import select
from uuid import UUID
from typing import Optional
from fastapi.responses import FileResponse
from services.listenbrainz_service import ListenBrainzService
router = APIRouter(
    prefix="/music",
    tags=["music"]
)

@router.get("/albums/{album_uuid}", response_model=AlbumRead)
async def get_album(
    album_uuid: UUID,
    should_hydrate: bool = False,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Fetch a single album."""
    music_service = MusicService(db)
    return await music_service.get_album(album_uuid, should_hydrate)


@router.get("/file/{library_track_uuid}")
async def stream_file(
    library_track_uuid: UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """Stream a file from the library by LibraryTrack UUID."""
    result = await db.execute(
        select(LibraryTrack).where(LibraryTrack.library_track_uuid == library_track_uuid)
    )
    ltrack = result.scalar_one_or_none()
    if not ltrack or not ltrack.path:
        raise HTTPException(404, "File not found")

    return FileResponse(ltrack.path, headers={"Accept-Ranges": "bytes"})


@router.get("/artists/{artist_uuid}", response_model=ArtistRead)
async def get_artist(
    artist_uuid: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Fetch a single artist."""
    music_service = MusicService(db)
    return await music_service.get_artist(artist_uuid)



@router.get("/tracks/{track_uuid}", response_model=TrackRead)
async def get_track(
    track_uuid: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    """Fetch a single track."""
    music_service = MusicService(db)
    return await music_service.get_track(track_uuid)


@router.get("/search/", response_model=MusicSearchResponse)
async def search(
    query: str = Query(..., min_length=2),
    limit: int = Query(25, le=100),
    only_digital: bool = True,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """Search albums, artists, and tracks by name/title (ILIKE)."""
    music_service = MusicService(db)
    return await music_service.search(query=query, limit=limit, only_digital=only_digital)

@router.get(
    "/artists/{artist_uuid}/similar",
    response_model=list[RecommendedArtist]
)
async def get_similar_artists(
    artist_uuid: UUID,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    """
    Fetch similar artists for a given artist.
    Returns full ArtistRead objects with score.
    """
    lb_service = ListenBrainzService(db)
    bridges = await lb_service.get_or_create_similar_artists(artist_uuid=artist_uuid)

    artists: list[RecommendedArtist] = []
    for b in bridges:
        if b.similar_artist:
            artists.append(
                RecommendedArtist(
                    score=b.score,
                    **b.similar_artist.__dict__,
                )
            )
    return artists
