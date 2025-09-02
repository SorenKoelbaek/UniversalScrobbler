# services/listen_service.py

import logging
from sqlmodel import select
from models.sqlmodels import TrackVersion, PlaybackHistory, Album
from services.musicbrainz_service import MusicBrainzService
from services.device_service import DeviceService
from dependencies.musicbrainz_api import MusicBrainzAPI
from datetime import datetime

logger = logging.getLogger(__name__)

class ListenService:
    def __init__(self, db):
        self.db = db
        self.mb_service = MusicBrainzService(db, MusicBrainzAPI())
        self.device_service = DeviceService(db)

    async def process_listen(self, user, listen_event: dict):
        """
        Main entrypoint for handling a listen (formerly 'scrobble').
        Ensures the track, album, and release exist and records playback history.
        """

        track_mbid = listen_event.track.mbid
        album_mbid = listen_event.album.mbid

        # 1. Try direct TrackVersion by recording MBID
        track_version = await self.db.scalar(
            select(TrackVersion).where(TrackVersion.recording_id == track_mbid)
        )

        album = None
        album_release = None

        if track_version:
            logger.info(f"✅ Found existing TrackVersion for recording MBID={track_mbid}")
            album_release = track_version.album_releases[0] if track_version.album_releases else None
            album = album_release.album if album_release else None
        else:
            # 2. Not found → pull via release MBID
            logger.info(f"ℹ️ No TrackVersion for MBID={track_mbid}, importing release={album_mbid}")
            album, album_release = await self.mb_service.get_or_create_album_from_musicbrainz_release(album_mbid)
            # After this, TrackVersions for all tracks on the release should exist
            track_version = await self.db.scalar(
                select(TrackVersion).where(TrackVersion.recording_id == track_mbid)
            )
            if not track_version:
                logger.warning(f"⚠️ Still no TrackVersion for recording={track_mbid} after import")
                return None

        # 3. Resolve or create device
        device = await self.device_service.get_or_create_device(
            user=user,
            device_id="listen_ingest",
            device_name=listen_event.source or "unknown"
        )

        # 4. Insert PlaybackHistory row
        played_at = listen_event.played_at.replace(tzinfo=None)
        history = PlaybackHistory(
            user_uuid=user.user_uuid,
            track_uuid=track_version.track_uuid,
            album_uuid=album.album_uuid if album else None,
            device_name = listen_event.source or "unknown",
            device_uuid=device.device_uuid,
            full_play=True,
            is_still_playing=False,
            played_at=played_at,
        )
        self.db.add(history)
        await self.db.commit()

        logger.info(f"🎧 Recorded listen for user={user.username}, track={listen_event.track.name}")
        return history
