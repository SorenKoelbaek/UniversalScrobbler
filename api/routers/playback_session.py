# routers/playback_session.py
from fastapi import APIRouter, Depends, Header, Request, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from dependencies.redis import get_redis
from services.device_service import DeviceService
from redis.asyncio import Redis
from models.sqlmodels import User
from models.appmodels import PlayRequest, SeekRequest, DeviceSwitchRequest
from services.playback_service import PlaybackService
from uuid import UUID
from typing import Optional
import hashlib

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback-sessions", tags=["playback-sessions"])



def get_playback_service(
    db: AsyncSession = Depends(get_async_session),
    r: Redis = Depends(get_redis),
) -> PlaybackService:
    return PlaybackService(db, r)

def _hash_user_agent(agent: str) -> str:
    """Generate a deterministic device_id from a User-Agent string."""
    return hashlib.sha1(agent.encode("utf-8")).hexdigest()

def _prettify_device_names(agent: str) -> str:
    agent_lower = agent.lower()

    # --- detect platform ---
    if "iphone" in agent_lower or "ipad" in agent_lower:
        platform = "iOS"
    elif "android" in agent_lower:
        platform = "Android"
    elif "windows" in agent_lower:
        platform = "Windows"
    elif "macintosh" in agent_lower or "mac os" in agent_lower:
        platform = "macOS"
    elif "linux" in agent_lower:
        platform = "Linux"
    else:
        platform = "Unknown Device"

    # --- detect browser ---
    if "firefox" in agent_lower:
        browser = "Firefox"
    elif "chrome" in agent_lower and "safari" in agent_lower:
        browser = "Chrome"
    elif "safari" in agent_lower and "version" in agent_lower:
        browser = "Safari"
    elif "edg" in agent_lower:
        browser = "Edge"
    else:
        browser = "Unknown Browser"

    return f"{platform} ({browser})"

def get_device_context(
    request: Request,
    device_id: Optional[str] = Header(None, alias="X-Device-Id"),
    device_name: Optional[str] = Header(None, alias="X-Device-Name"),
) -> dict:
    """
    Resolve device context for this request.
    Priority:
    1. Explicit headers (X-Device-Id / X-Device-Name)
    2. User-Agent header → hash for device_id, prettified for device_name
    """
    if device_id and device_name:
        return {"device_id": device_id, "device_name": device_name}

    user_agent = request.headers.get("user-agent", "Unknown Client")

    return {
        "device_id": _hash_user_agent(user_agent),     # ✅ unique id from hash
        "device_name": _prettify_device_names(user_agent),  # ✅ nice readable name
    }

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
    device: dict = Depends(get_device_context),
):
    """Replace queue with track/album/artist and start playing."""
    return await playback_service.play(current_user.user_uuid, body, device)


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
    device: dict = Depends(get_device_context),
):
    state = await playback_service.jump_to(current_user.user_uuid, UUID(body["playback_queue_uuid"]), device)
    return state

@router.post("/seek")
async def seek(
    body: SeekRequest,
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    device: dict = Depends(get_device_context),
):
    """Seek to a position (in ms) in the current track."""
    return await playback_service.seek(current_user.user_uuid, body.position_ms, device)


@router.post("/resume")
async def resume(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    device: dict = Depends(get_device_context),
):
    """Resume playback for the current user."""
    return await playback_service.resume(current_user.user_uuid, device)


@router.post("/pause")
async def pause(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    device: dict = Depends(get_device_context),
):
    """Pause playback for the current user."""
    return await playback_service.pause(current_user.user_uuid, device)


@router.post("/next")
async def next_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    device: dict = Depends(get_device_context),
):
    """Skip to the next track in the queue (resets position to 0)."""
    return await playback_service.next(current_user.user_uuid, device)


@router.post("/previous")
async def previous_track(
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
    device: dict = Depends(get_device_context),
):
    """Go back to the previous track (resets position to 0)."""
    return await playback_service.previous(current_user.user_uuid, device)

@router.post("/reorder")
async def reorder_queue(
    body: dict,  # { "queue": [uuid1, uuid2, ...] }
    current_user: User = Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    state = await playback_service.reorder(current_user.user_uuid, body["queue"])
    return state


@router.post("/switch")
async def switch_active_device(
    body: DeviceSwitchRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user=Depends(get_current_user),
    playback_service: PlaybackService = Depends(get_playback_service),
):
    """
    Switch the active playback device for the current user.
    """
    user_uuid = current_user.user_uuid

    service = DeviceService(db)
    session = await service.switch_active_device(user_uuid, body.device_uuid)

    if not session.active_device_uuid:
        raise HTTPException(status_code=400, detail="Failed to set active device")

    await playback_service._publish(user_uuid, "timeline", rev=1)

    return {"status": "ok", "active_device_uuid": str(session.active_device_uuid)}