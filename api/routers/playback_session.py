# routers/playback_session.py
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from dependencies.redis import get_redis
from redis.asyncio import Redis
from models.sqlmodels import User
from models.appmodels import PlayRequest, SeekRequest
from services.playback_service import PlaybackService

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback-sessions", tags=["playback-sessions"])


def get_playback_service(
    db: AsyncSession = Depends(get_async_session),
    r: Redis = Depends(get_redis),
) -> PlaybackService:
    """Provide PlaybackService with DB + Redis."""
    return PlaybackService(db, r)


@router.post("/seek")
async def seek(
    body: SeekRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Seek to a position (in ms) in the current track."""
    state = await playback_service.seek(current_user.user_uuid, body.position_ms)
    return state

@router.get("/")
async def get_playback_session(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Return the current playback state for the authenticated user."""
    state = await playback_service.get_state(current_user.user_uuid)
    return state


@router.post("/play")
async def play(
    body: PlayRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Start playback (track, album, or artist)."""
    state = await playback_service.play(current_user.user_uuid, body)
    return state

@router.post("/resume")
async def resume(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Start playback (track, album, or artist)."""
    state = await playback_service.resume(current_user.user_uuid)
    return state


@router.post("/pause")
async def pause(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Pause playback for the current user."""
    state = await playback_service.pause(current_user.user_uuid)
    return state


@router.post("/next")
async def next_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Skip to the next track in the user’s queue."""
    state = await playback_service.next(current_user.user_uuid)
    return state


@router.post("/previous")
async def previous_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Go back to the previous track in the user’s queue."""
    state = await playback_service.previous(current_user.user_uuid)
    return state
