# routers/listen.py

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.database import get_async_session
from dependencies.auth import get_current_user
from models.sqlmodels import User
from models.appmodels import PlaybackHistorySimple, RecommendedArtist
from services.listen_service import ListenService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/listen", tags=["listen"])


def get_listen_service(
    db: AsyncSession = Depends(get_async_session),
) -> ListenService:
    return ListenService(db)


@router.get("/", response_model=List[PlaybackHistorySimple])
async def list_recent_listens(
    days: int = 7,
    current_user: User = Depends(get_current_user),
    listen_service: ListenService = Depends(get_listen_service),
):
    """
    Get the most recent listens for the authenticated user.
    """
    listens = await listen_service.get_recent_listens(current_user, days=days)
    return listens

@router.get("/recommended-artists", response_model=List[RecommendedArtist])
async def get_recommended_artists(
    days: int = 7,
    limit: int = 15,
    current_user: User = Depends(get_current_user),
    listen_service: ListenService = Depends(get_listen_service),
):
    """
    Get recommended artists for the authenticated user.
    Recommendations are based on their listens in the last `days` period,
    combined with ListenBrainz similar-artist scores.
    """
    return await listen_service.get_user_recommended_artists(
        user_uuid=current_user.user_uuid,
        limit=limit,
        days=days,
    )