from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse
from services.discogs_service import DiscogsService
from services.collection_service import CollectionService
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


@router.get("/login")
async def get_login_url(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    discogs_service = DiscogsService(db)

    url = await discogs_service.get_redirect_url(user.user_uuid, db)
    return {"url": url}


@router.post("/authorize")
async def authorize_discogs(
    payload: DiscogsAuthRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user),
):
    discogs_service = DiscogsService(db)
    return await discogs_service.authorize_user(
        oauth_token=payload.oauth_token,
        oauth_verifier=payload.oauth_verifier,
        user_uuid=user.user_uuid,
        db=db,
    )

@router.post("/refresh/")
async def process_collection(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    collection_service = CollectionService(db=db)
    background_tasks.add_task(collection_service.process_collection, user.user_uuid)
    return {"message": "Discogs collection refresh triggered in background."}


@router.get("/me/")
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    discogs_service = DiscogsService(db)
    identity = await discogs_service.get_identity(user.user_uuid, db)
    return identity