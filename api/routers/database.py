from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from models.appmodels import CollectionRead, CollectionSimple
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from models.sqlmodels import *
from sqlmodel import select, delete
from config import settings
import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/database",
    tags=["database"]
)

@router.delete("/delete_all")
async def delete_all(db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    try:
        if user.username == "sorenkoelbaek":
            # Deleting all records from the tables excluding User, SpotifyToken, DiscogsToken
            await db.execute(delete(ArtistBridge))
            await db.execute(delete(AlbumArtistBridge))
            await db.execute(delete(AlbumReleaseArtistBridge))
            await db.execute(delete(TrackArtistBridge))
            await db.execute(delete(TrackVersionExtraArtist))
            await db.execute(delete(TrackAlbumBridge))
            await db.execute(delete(CollectionAlbumBridge))
            await db.execute(delete(CollectionAlbumReleaseBridge))
            await db.execute(delete(TrackVersionAlbumReleaseBridge))
            await db.execute(delete(TrackVersion))
            await db.execute(delete(Track))
            await db.execute(delete(Collection))
            await db.execute(delete(AlbumRelease))
            await db.execute(delete(Album))
            await db.execute(delete(Artist))

            # Commit the changes
            await db.commit()

            return {"status": "success", "message": "All records have been deleted."}
        else:
            raise HTTPException(status_code=403, detail="Unauthorized user")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")