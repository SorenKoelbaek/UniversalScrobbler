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
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback-sessions", tags=["playback-sessions"])


def get_playback_service(
    db: AsyncSession = Depends(get_async_session),
    r: Redis = Depends(get_redis),
) -> PlaybackService:
    return PlaybackService(db, r)


@router.get("/")
async def get_playback_session(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Return the current playback state for the authenticated user."""
    return await playback_service.get_state(current_user.user_uuid)


@router.post("/play")
async def play(
    body: PlayRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Replace queue with track/album/artist and start playing."""
    return await playback_service.play(current_user.user_uuid, body)


@router.post("/queue")
async def add_to_queue(
    body: PlayRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Append track/album/artist to the existing queue without starting playback."""
    return await playback_service.add_to_queue(current_user.user_uuid, body)

@router.post("/jump")
async def jump_to_track(
    body: dict,  # { "playback_queue_uuid": "..." }
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    state = await playback_service.jump_to(current_user.user_uuid, UUID(body["playback_queue_uuid"]))
    return state

@router.post("/seek")
async def seek(
    body: SeekRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Seek to a position (in ms) in the current track."""
    return await playback_service.seek(current_user.user_uuid, body.position_ms)


@router.post("/resume")
async def resume(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Resume playback for the current user."""
    return await playback_service.resume(current_user.user_uuid)


@router.post("/pause")
async def pause(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Pause playback for the current user."""
    return await playback_service.pause(current_user.user_uuid)


@router.post("/next")
async def next_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Skip to the next track in the queue (resets position to 0)."""
    return await playback_service.next(current_user.user_uuid)


@router.post("/previous")
async def previous_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """Go back to the previous track (resets position to 0)."""
    return await playback_service.previous(current_user.user_uuid)

@router.post("/reorder")
async def reorder_queue(
    body: dict,  # { "queue": [uuid1, uuid2, ...] }
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    state = await playback_service.reorder(current_user.user_uuid, body["queue"])
    return state