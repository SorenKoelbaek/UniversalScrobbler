from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, UTC
from dependencies.auth import get_current_user
from models.appmodels import AlbumFindSimilarRequest, PlaybackHistorySimple, CurrentlyPlaying, PaginatedResponse, AlbumRead
from typing import List
from services.playback_history_service import PlaybackHistoryService
from dependencies.database import get_async_session
from services.music_service import MusicService
from sqlalchemy import select
from models.sqlmodels import User

router = APIRouter(
    prefix="/consumption",
    tags=["consumption"],
)


@router.get("/history", response_model=PaginatedResponse[PlaybackHistorySimple])
async def get_consumption_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    service = PlaybackHistoryService(db)
    return await service.get_user_playback_history(user, offset=offset, limit=limit)



@router.get("/currently-playing", response_model=PlaybackHistorySimple)
async def get_currently_playing(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    service = PlaybackHistoryService(db)
    result = await service.get_currently_playing(user)
    if not result:
        raise HTTPException(status_code=404, detail="No playback history found.")
    return result

@router.get("/recommendations", response_model=PaginatedResponse[AlbumRead])
async def get_consumption_based_recommendations(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
    alpha: float = Query(1.0),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    playback_service = PlaybackHistoryService(db)
    music_service = MusicService(db)

    try:
        v_query, exclude_album_uuids = await playback_service.get_taste_vector_for_user(
            user=user,
            alpha=alpha,
        )
    except HTTPException as e:
        raise e

    return await music_service.get_album_recommendations_from_vector(
        v_query=v_query,
        limit=limit,
        offset=offset,
        exclude_album_uuids=exclude_album_uuids
    )

@router.get("/by-album/{album_uuid}", response_model=PaginatedResponse[AlbumRead])
async def get_recommendations_by_album(
    album_uuid: UUID = Path(..., description="UUID of the reference album"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    music_service = MusicService(db)
    return await music_service.get_album_recommendations_for_album(album_uuid, limit=limit)


@router.post("/recommendations/", response_model=PaginatedResponse[AlbumRead])
async def get_recommendations_by_album(
    findSimilar: AlbumFindSimilarRequest,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    music_service = MusicService(db)
    return await music_service.find_similar_albums(findSimilar, limit=limit)
