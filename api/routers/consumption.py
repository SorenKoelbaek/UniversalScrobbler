from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session
from datetime import datetime, timedelta, UTC
from dependencies.auth import get_current_user
from models.appmodels import PlaybackHistoryRead, CurrentlyPlaying
from models.sqlmodels import User
from typing import List
from services.playback_history_service import PlaybackHistoryService
from dependencies.database import get_async_session

router = APIRouter(
    prefix="/consumption",
    tags=["consumption"],
)


@router.get("/top-tracks")
async def get_top_tracks(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    service = PlaybackHistoryService(db)
    return await service.get_top_tracks(user, days)


@router.get("/history", response_model=List[PlaybackHistoryRead])
async def get_consumption_history(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_async_session),
):
    service = PlaybackHistoryService(db)
    return await service.get_user_playback_history(user, days)


@router.get("/currently-playing", response_model=CurrentlyPlaying)
async def get_currently_playing(
    db: Session = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    service = PlaybackHistoryService(db)
    result = service.get_currently_playing(user)
    if not result:
        raise HTTPException(status_code=404, detail="No playback history found.")
    return result
