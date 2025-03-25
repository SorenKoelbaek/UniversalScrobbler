import logging
from sqlmodel import Session, select
from services.spotify_service import SpotifyService
from models.sqlmodels import User, PlaybackHistory
from sqlmodel.ext.asyncio.session import AsyncSession
from dependencies.database import get_async_engine
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

async def gather_playback_for_user(session: Session, user_uuid: str, limit: int):
    spotify_service = SpotifyService()

    try:
        await spotify_service.gather_user_playback_history(user_uuid, session, limit)
        logger.info(f"Playback history gathered for user {user_uuid}")
    except Exception as e:
        logger.error(f"Error gathering playback history for user {user_uuid}: {e}")
        raise


async def gather_all_playbacks():
    engine = get_async_engine()
    async with AsyncSession(engine) as session:
        result = await session.exec(select(User))
        users = result.all()

        logger.info(f"Found {len(users)} users")
        if not users:
            logger.info("No users found in the database.")
            return

        for user in users:
            user_uuid = user.user_uuid
            logger.info(f"🎧 Gathering playback history for user {user_uuid}...")
            await gather_playback_for_user(session, user_uuid, limit=50)

