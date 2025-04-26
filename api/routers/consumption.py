from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, UTC
from dependencies.auth import get_current_user
from models.appmodels import PlaybackHistorySimple, CurrentlyPlaying, PaginatedResponse
from models.sqlmodels import User
from typing import List
from services.playback_history_service import PlaybackHistoryService
from dependencies.database import get_async_session

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
