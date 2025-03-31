from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from services.discogs_service import DiscogsService
from fastapi import Depends, Request
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from sqlmodel.ext.asyncio.session import AsyncSession
from models.sqlmodels import User
from models.appmodels import DiscogsAuthRequest, TrackRead
from sqlmodel import Session, select
from typing import Optional

router = APIRouter(
    prefix="/discogs",
    tags=["discogs"]
)

discogs_service = DiscogsService()

@router.get("/login")
async def get_login_url(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    url = await discogs_service.get_redirect_url(user.user_uuid, db)
    return {"url": url}


@router.post("/authorize")
async def authorize_discogs(
    payload: DiscogsAuthRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    return await discogs_service.authorize_user(
        oauth_token=payload.oauth_token,
        oauth_verifier=payload.oauth_verifier,
        user_uuid=user.user_uuid,
        db=db,
    )



@router.post("/refresh/")
async def refresh_collection(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    background_tasks.add_task(discogs_service.update_user_collection, user.user_uuid, db)
    return {"message": "Discogs collection refresh triggered in background."}

@router.get("/search/",  response_model=TrackRead)
async def search(
    track_name: Optional[str] = None,
    artist_name: Optional[str] = None,
    album_name: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    search_result = await discogs_service.get_data_from_discogs(user.user_uuid, db, artist_name, album_name, track_name)

    return search_result


@router.get("/me/")
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    identity = await discogs_service.get_identity(user.user_uuid, db)
    return identity