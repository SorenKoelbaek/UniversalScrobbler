# routers/playback_session.py
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from dependencies.redis import get_redis
from redis.asyncio import Redis
from models.sqlmodels import User
from models.appmodels import PlayRequest
from services.playback_service import PlaybackService

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback-sessions", tags=["playback-sessions"])


def get_playback_service(r: Redis = Depends(get_redis)) -> PlaybackService:
    """Dependency wrapper for PlaybackService, backed by Redis."""
    return PlaybackService(r)


@router.get("/me")
async def get_playback_session(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    db: AsyncSession = Depends(get_async_session),  # keep if needed for later DB lookups
):
    """Return the current playback state for the authenticated user."""
    state = await playback_service.get_state(current_user.user_uuid)
    return state


@router.post("/me/play")
async def play_track(
    body: PlayRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    db: AsyncSession = Depends(get_async_session),
):
    """Start playback of a specific track."""
    state = await playback_service.play_track(current_user.user_uuid, body.track_uuid)
    return state


@router.post("/me/pause")
async def pause_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Pause playback for the current user."""
    state = await playback_service.pause(current_user.user_uuid)
    return state


@router.post("/me/next")
async def next_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Skip to the next track in the user’s queue."""
    state = await playback_service.next(current_user.user_uuid)
    return state


@router.post("/me/previous")
async def previous_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Go back to the previous track in the user’s queue."""
    state = await playback_service.previous(current_user.user_uuid)
    return state
