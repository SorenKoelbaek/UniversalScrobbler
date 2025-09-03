from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import CollectionRead, CollectionSimpleRead, PaginatedResponse, AlbumFlat
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from models.sqlmodels import User
from services.collection_service import CollectionService
from sqlmodel import select
from uuid import UUID
from fastapi import Query
import logging


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/collection",
    tags=["collection"]
)

@router.get("/", response_model=PaginatedResponse[AlbumFlat])
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

@router.post("/scan")
async def scan_collection_directory(
    overwrite: bool,
    background_tasks: BackgroundTasks,
    collection_id: UUID | None = None,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    collection_service = CollectionService(db)
    user_id = user.user_uuid

    async def task():
        logger.info("Starting background scan...")
        await collection_service.scan_directory(
            collection_id=collection_id,
            user_uuid=user_id,
            overwrite=overwrite
        )
        logger.info("Background scan finished.")

    background_tasks.add_task(task)
    return {"status": "scan started in background"}