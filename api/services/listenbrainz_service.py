# services/listenbrainz_service.py

import logging
from datetime import datetime, timedelta
from itertools import islice
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select, delete

from dependencies.listenbrainz_api import listenbrainz_api
from dependencies.musicbrainz_api import musicbrainz_api
from services.musicbrainz_service import MusicBrainzService
from models.sqlmodels import Artist, SimilarArtistBridge, Album

logger = logging.getLogger(__name__)


class ListenBrainzService:
    """
    Service for fetching and caching similar artists from ListenBrainz.
    NOTE: We no longer keep a long-lived AsyncSession on self.
    Each call uses the provided session explicitly, avoiding concurrent reuse.
    """

    def __init__(self, mb_service_factory=MusicBrainzService):
        self.mb_service_factory = mb_service_factory

    async def get_or_create_similar_artists(
        self, artist_uuid: UUID, db: AsyncSession
    ) -> list[SimilarArtistBridge]:
        """
        Return SimilarArtistBridge rows (with .similar_artist and their albums eagerly loaded).
        If cache is older than 30 days, refresh from ListenBrainz.
        Skips unresolved artists instead of inserting NULL artist_uuid.
        """

        # Step 1. resolve MBID of reference artist
        stmt = select(Artist).where(Artist.artist_uuid == artist_uuid)
        result = await db.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist or not artist.musicbrainz_artist_id:
            logger.warning(f"⚠️ No MBID for artist {artist_uuid}, skipping similar fetch")
            return []

        artist_mbid = artist.musicbrainz_artist_id

        # Step 2. check cache (with eager loading)
        stmt = (
            select(SimilarArtistBridge)
            .where(SimilarArtistBridge.reference_artist_uuid == artist_uuid)
            .options(
                selectinload(SimilarArtistBridge.similar_artist)
                .selectinload(Artist.albums)
                .options(
                    selectinload(Album.artists),
                    selectinload(Album.types),
                    selectinload(Album.releases),
                ),
                selectinload(SimilarArtistBridge.reference_artist),
            )
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if rows and rows[0].fetched_at > datetime.utcnow() - timedelta(days=30):
            logger.debug(f"✅ Using cached similar artists for {artist.name} ({artist_mbid})")
            return rows

        # Step 3. fetch from ListenBrainz
        data = await listenbrainz_api.get_similar_artist(artist_mbid)
        if not data:
            logger.error(f"❌ No similar artists returned for {artist.name} ({artist_mbid})")
            return rows  # return stale cache if present

        # Step 4. clear old cache
        await db.execute(
            delete(SimilarArtistBridge).where(
                SimilarArtistBridge.reference_artist_uuid == artist_uuid
            )
        )

        # Step 5. insert new rows
        mb_service = self.mb_service_factory(db, api=musicbrainz_api)
        new_rows: list[SimilarArtistBridge] = []

        for d in islice(data, 15):  # ✅ only process first 15
            mbid = d.get("artist_mbid")
            db_artist = None

            if mbid:
                result = await db.execute(
                    select(Artist).where(Artist.musicbrainz_artist_id == mbid)
                )
                db_artists = result.scalars().all()

                if len(db_artists) == 1:
                    db_artist = db_artists[0]
                elif len(db_artists) > 1:
                    db_artist = db_artists[0]
                    logger.warning(
                        f"⚠️ Multiple artists with MBID {mbid}, using {db_artist.artist_uuid} ({db_artist.name})"
                    )

                if not db_artist:
                    try:
                        db_artist = await mb_service.get_or_create_artist_by_mbid(mbid)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to fetch MB artist {mbid}: {e}")

            if not db_artist:
                logger.debug(f"⏭ Skipping similar artist {mbid} (unresolved)")
                continue

            sa = SimilarArtistBridge(
                reference_artist_uuid=artist_uuid,
                artist_uuid=db_artist.artist_uuid,
                score=d.get("score", 0),
                fetched_at=datetime.utcnow(),
                reference_mbid=d.get("reference_mbid"),
                comment=d.get("comment"),
                type=d.get("type"),
            )
            db.add(sa)
            new_rows.append(sa)

        await db.commit()

        # Step 6. reload with albums eagerly loaded
        result = await db.execute(stmt)
        return result.scalars().all()
