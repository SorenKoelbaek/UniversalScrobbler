from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import CollectionRead, CollectionSimpleRead, PaginatedResponse, AlbumReleaseFlat
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from models.sqlmodels import User
from services.collection_service import CollectionService
from sqlmodel import select
from uuid import UUID
from fastapi import Query

router = APIRouter(
    prefix="/collection",
    tags=["collection"]
)

@router.get("/", response_model=PaginatedResponse[AlbumReleaseFlat])
async def get_my_collections(
    search: str = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),

    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    collection_service = CollectionService(db)

    return await collection_service.get_primary_collection(
        user.user_uuid, offset=offset, limit=limit, search=search)
