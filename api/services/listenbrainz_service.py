import logging
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from itertools import islice
from dependencies.listenbrainz_api import listenbrainz_api
from services.musicbrainz_service import MusicBrainzService
from dependencies.musicbrainz_api import musicbrainz_api
from models.sqlmodels import Artist, SimilarArtistBridge

logger = logging.getLogger(__name__)


class ListenBrainzService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.mb_service = MusicBrainzService(db, api=musicbrainz_api)

    async def get_or_create_similar_artists(self, artist_uuid: UUID) -> list[SimilarArtistBridge]:
        # Step 1. resolve MBID of reference artist
        stmt = select(Artist).where(Artist.artist_uuid == artist_uuid)
        result = await self.db.execute(stmt)
        artist = result.scalar_one_or_none()

        if not artist or not artist.musicbrainz_artist_id:
            logger.warning(f"⚠️ No MBID for artist {artist_uuid}, skipping similar fetch")
            return []

        artist_mbid = artist.musicbrainz_artist_id

        # Step 2. check cache
        stmt = select(SimilarArtistBridge).where(
            SimilarArtistBridge.reference_artist_uuid == artist_uuid
        )
        result = await self.db.execute(stmt)
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
        await self.db.execute(
            delete(SimilarArtistBridge).where(
                SimilarArtistBridge.reference_artist_uuid == artist_uuid
            )
        )

        # Step 5. insert new rows
        new_rows = []

        for d in islice(data, 15):  # ✅ only process first 15
            similar_artist_uuid = None
            mbid = d.get("artist_mbid")

            if mbid:
                # 🔑 Ensure artist exists in DB — create via MB service if missing
                result = await self.db.execute(
                    select(Artist).where(Artist.musicbrainz_artist_id == mbid)
                )
                db_artist = result.scalar_one_or_none()

                if not db_artist:
                    try:
                        db_artist = await self.mb_service.get_or_create_artist_by_mbid(mbid)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to fetch MB artist {mbid}: {e}")

                if db_artist:
                    similar_artist_uuid = db_artist.artist_uuid

            sa = SimilarArtistBridge(
                reference_artist_uuid=artist_uuid,
                artist_uuid=similar_artist_uuid,
                score=d.get("score", 0),
                fetched_at=datetime.utcnow(),
                reference_mbid=d.get("reference_mbid"),
                comment=d.get("comment"),
                type=d.get("type"),
            )
            self.db.add(sa)
            new_rows.append(sa)

        await self.db.commit()
        return new_rows
