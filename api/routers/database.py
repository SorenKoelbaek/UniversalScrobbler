from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from services.musicbrainz_service import MusicBrainzService
from models.appmodels import CollectionRead, CollectionSimple
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from dependencies.musicbrainz_api import MusicBrainzAPI
from models.sqlmodels import *
from sqlmodel import select, delete
from config import settings
import logging
logger = logging.getLogger(__name__)
from scripts.import_collection import ImportCollection
import asyncio
router = APIRouter(
    prefix="/database",
    tags=["database"]
)


@router.put("/import_musicbrainz")
async def import_database_background(db: AsyncSession = Depends(get_async_session)):
    async def run_import_sequence():
        try:
            import_collection = ImportCollection(db)
            await import_collection.import_data("artist")
            await import_collection.import_data("release-group")
            await import_collection.import_data("release")
            logger.info("Import completed successfully.")
        except Exception as e:
            logger.exception("Error during background import: %s", e)

    # Launch the import task in the background
    asyncio.create_task(run_import_sequence())

    return {"success": True, "message": "Import started in background"}


@router.delete("/delete_all")
async def delete_all(db: AsyncSession = Depends(get_async_session), user: User = Depends(get_current_user)):
    try:
        if user.username == "sorenkoelbaek":
            # Deleting all records from the tables excluding User, SpotifyToken, DiscogsToken
            await db.execute(delete(PlaybackHistory))
            await db.execute(delete(ArtistBridge))
            await db.execute(delete(AlbumArtistBridge))
            await db.execute(delete(AlbumReleaseArtistBridge))
            await db.execute(delete(TrackArtistBridge))
            await db.execute(delete(TrackVersionExtraArtist))
            await db.execute(delete(TrackAlbumBridge))
            await db.execute(delete(CollectionAlbumBridge))
            await db.execute(delete(CollectionAlbumReleaseBridge))
            await db.execute(delete(TrackVersionAlbumReleaseBridge))
            await db.execute(delete(TrackVersionTagBridge))
            await db.execute(delete(TrackVersionGenreBridge))
            await db.execute(delete(TrackVersion))
            await db.execute(delete(AlbumTagBridge))
            await db.execute(delete(AlbumGenreBridge))
            await db.execute(delete(AlbumReleaseTagBridge))
            await db.execute(delete(AlbumReleaseGenreBridge))
            await db.execute(delete(ArtistTagBridge))
            await db.execute(delete(Tag))
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