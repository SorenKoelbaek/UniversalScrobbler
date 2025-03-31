from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import CollectionRead, CollectionSimple
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from models.sqlmodels import User
from services.collection_service import CollectionService
from sqlmodel import select
from uuid import UUID

router = APIRouter(
    prefix="/collection",
    tags=["collection"]
)

@router.get("/", response_model=CollectionSimple)
async def get_my_collections(db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch a single album."""
    collection_service = CollectionService(db)
    return await collection_service.get_primary_collection(user.user_uuid)

@router.get("/{collection_uuid}", response_model=CollectionSimple)
async def get_collection(collection_uuid: UUID, db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    """Fetch a single album."""
    collection_service = CollectionService(db)
    return await collection_service.get_collection(collection_uuid)
