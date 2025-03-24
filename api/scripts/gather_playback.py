import logging
from sqlmodel import Session, select
from services.spotify_service import SpotifyService
from dependencies.database import _get_engine
from models.sqlmodels import User

logger = logging.getLogger(__name__)

def gather_playback_for_user(session: Session, user_uuid: str, limit: int):
    """
    Gather recent playback history for a user (called manually from the command line).
    """
    spotify_service = SpotifyService()

    try:
        # Gather playback history for the user
        spotify_service.gather_user_playback_history(user_uuid, session, limit)
        logger.info(f"Playback history gathered for user {user_uuid}")
    except Exception as e:
        logger.error(f"Error gathering playback history for user {user_uuid}: {e}")
        raise

def gather_all_playbacks():
    engine = _get_engine(True)
    with Session(engine) as session:
        users = session.exec(select(User)).all()  # Get all users

        if not users:
            logger.info("No users found in the database.")
            return

        # Loop over each user and gather playback history
        for user in users:
            user_uuid = user.user_uuid
            logger.info(f"🎧 Gathering playback history for user {user_uuid}...")
            gather_playback_for_user(session, user_uuid, limit=50)

if __name__ == "__main__":
    gather_all_playbacks()
