from sqlalchemy import func, or_, exists
from sqlalchemy.orm import selectinload

from models.sqlmodels import Collection, Album, CollectionAlbumReleaseBridge, Artist, AlbumRelease, \
    AlbumReleaseArtistBridge, AlbumArtistBridge, CollectionAlbumBridge, CollectionAlbumFormat
from models.appmodels import CollectionSimple, CollectionSimpleRead, PaginatedResponse, AlbumFlat
from uuid import UUID
from fastapi import HTTPException
import csv
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, delete
from sqlalchemy.dialects.postgresql import insert
from mutagen import File as MutagenFile
import os
import asyncio
import re
from dependencies.musicbrainz_api import MusicBrainzAPI
from dependencies.discogs_api import DiscogsAPI
from models.sqlmodels import DiscogsToken, Collection, CollectionTrack
from services.musicbrainz_service import MusicBrainzService
from services.discogs_service import DiscogsService
from config import settings
import logging
logger = logging.getLogger(__name__)

discogs_api = DiscogsAPI()

class CollectionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.musicbrainz_service = MusicBrainzService(db, MusicBrainzAPI())
        self.discogs_service = DiscogsService(db, discogs_api)

    async def get_or_create_collection(self, user_uuid: str, collection_name: str):
        """Helper function to check if a user exists and create it if not."""
        result = await self.db.execute(select(Collection).where(Collection.user_uuid == user_uuid))
        collection = result.scalars().first()
        if not collection:
            collection = Collection(user_uuid=user_uuid, collection_name=collection_name)
            self.db.add(collection)
            await self.db.commit()

        return await self.get_collection_simple(collection.collection_uuid)

    async def get_collection(self, collection_id: UUID) -> CollectionSimpleRead:
        result = await self.db.execute(
            select(Collection)
            .where(Collection.collection_uuid == collection_id)
            .options(
                selectinload(Collection.albums)
                .selectinload(Album.artists),
                selectinload(Collection.albums)
                .selectinload(Album.tracks),
                selectinload(Collection.albums)
                .selectinload(Album.collectionalbumbridge_collection)  # bridge
                .selectinload(CollectionAlbumBridge.formats),  # 🔥 load formats
                selectinload(Collection.album_releases)
                .selectinload(AlbumRelease.artists),
                selectinload(Collection.tracks)
                .selectinload(CollectionTrack.track_version)
                .selectinload(TrackVersion.album_releases),  # so releases are available
            )
        )
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        return CollectionSimpleRead.model_validate(collection)

    async def get_primary_collection(
            self,
            user_uuid: UUID,
            offset: int = 0,
            limit: int = 100,
            search: str | None = None,
    ) -> PaginatedResponse[AlbumFlat]:
        # Fetch the user's collection
        result = await self.db.execute(
            select(Collection).where(Collection.user_uuid == user_uuid)
        )
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        base_query = (
            select(Album)
            .join(AlbumRelease, Album.album_uuid == AlbumRelease.album_uuid)
            .join(CollectionAlbumReleaseBridge,
                  CollectionAlbumReleaseBridge.album_release_uuid == AlbumRelease.album_release_uuid)
            .where(CollectionAlbumReleaseBridge.collection_uuid == collection.collection_uuid)
        )

        if search:
            search_term = f"%{search.lower()}%"

            artist_match = exists(
                select(1)
                .select_from(AlbumArtistBridge)
                .join(Artist, AlbumArtistBridge.artist_uuid == Artist.artist_uuid)
                .where(AlbumArtistBridge.album_uuid == Album.album_uuid)
                .where(func.lower(Artist.name).ilike(search_term))
            )

            title_match = func.lower(Album.title).ilike(search_term)

            base_query = base_query.where(or_(title_match, artist_match))

        # Total count
        total_query = base_query.with_only_columns(
            func.count(func.distinct(Album.album_uuid))
        )
        total_result = await self.db.execute(total_query)
        total = total_result.scalar_one()

        # Apply pagination and eager loading
        albums_query = (
            base_query
            .distinct(Album.album_uuid)
            .offset(offset)
            .limit(limit)
            .options(
                selectinload(Album.artists),
                selectinload(Album.releases),
                selectinload(Album.collectionalbumbridge).selectinload(CollectionAlbumBridge.formats),
            )
        )

        albums_result = await self.db.execute(albums_query)
        albums = albums_result.scalars().all()

        return PaginatedResponse[AlbumFlat](
            total=total,
            offset=offset,
            limit=limit,
            items=[AlbumFlat.model_validate(a) for a in albums],
        )

    async def get_collection_simple(self, collection_id: UUID) -> CollectionSimple:
        result = await self.db.execute(
            select(Collection)
            .where(Collection.collection_uuid == collection_id)
            .options(
                selectinload(Collection.albums)
                .selectinload(Album.types),
                selectinload(Collection.album_releases),
                selectinload(Collection.tracks)
                .selectinload(CollectionTrack.track_version),
            )
        )
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionSimple.model_validate(collection)

    async def read_collection_from_csv(self, csv_file_path):
        collection = []
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if 'release_id' in row and row['release_id']:
                        try:
                            release_id = int(row['release_id'])
                            collection.append({
                                'discogs_release_id': release_id,
                                'artist': row.get('Artist', ''),
                                'title': row.get('Title', ''),
                                'label': row.get('Label', ''),
                                'format': row.get('Format', ''),
                                'catalog': row.get('Catalog#', ''),
                                'released': row.get('Released', '')
                            })
                        except ValueError:
                            print(f"Warning: Invalid release_id: {row['release_id']}")
                    else:
                        print("Warning: Row missing release_id")
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return None

        print(f"Loaded {len(collection)} releases from CSV file")
        return collection

    async def _link_release_to_collection(
            self,
            collection_id: UUID,
            album: Album,
            album_release: AlbumRelease,
            fmt: str = "digital",
            status: str = "owned",
    ):
        album_uuid = album.album_uuid
        album_release_uuid = album_release.album_release_uuid

        # Album bridge
        stmt = insert(CollectionAlbumBridge).values(
            album_uuid=album_uuid,
            collection_uuid=collection_id
        ).on_conflict_do_nothing()
        await self.db.execute(stmt)

        # Release bridge
        stmt = insert(CollectionAlbumReleaseBridge).values(
            album_release_uuid=album_release_uuid,
            collection_uuid=collection_id
        ).on_conflict_do_nothing()
        await self.db.execute(stmt)

        # Format
        stmt = insert(CollectionAlbumFormat).values(
            collection_uuid=collection_id,
            album_uuid=album_uuid,
            format=fmt,
            status=status
        ).on_conflict_do_nothing()
        await self.db.execute(stmt)

        await self.db.commit()

    async def process_collection(self, user_uuid: str, csv_file_path: str = None):
        if not user_uuid:
            raise HTTPException(status_code=400, detail="user_uuid is required")

        session = self.db
        matched_releases = []
        unmatched_releases = []

        discogs_api = DiscogsAPI()
        musicbrainz_api = MusicBrainzAPI()
        discogs_service = DiscogsService(session, discogs_api)
        musicbrainz_service = MusicBrainzService(session, musicbrainz_api)

        # Get auth
        result = await session.exec(select(DiscogsToken).where(DiscogsToken.user_uuid == user_uuid))
        auth = result.first()
        token = auth.access_token
        secret = auth.access_token_secret

        # Ensure collection exists
        collection = await self.get_or_create_collection(user_uuid, "Discogs main collection")

        # Either load from CSV or API
        collection_to_process = (
            await self.read_collection_from_csv(csv_file_path)
            if csv_file_path else
            discogs_api.get_collection(token, secret)
        )

        # Existing release IDs already linked
        existing_release_ids = {r.discogs_release_id for r in collection.album_releases}

        new_releases = [r for r in collection_to_process if r["discogs_release_id"] not in existing_release_ids]
        logger.info(f"Found {len(new_releases)} new releases to process")

        for index, release_info in enumerate(new_releases):
            discogs_release_id = release_info["discogs_release_id"]
            logger.info(f"Processing {index + 1}/{len(new_releases)}: Discogs ID {discogs_release_id}")

            try:
                # Already in DB?
                result = await session.exec(
                    select(AlbumRelease).where(AlbumRelease.discogs_release_id == discogs_release_id)
                )
                albumrelease = result.first()

                if albumrelease:
                    await self._link_release_to_collection(
                        collection.collection_uuid,
                        albumrelease.album,
                        albumrelease,
                        fmt="vinyl"
                    )
                    logger.info("✅ Linked existing album release (vinyl)")
                    continue

                # Try MB mapping
                await asyncio.sleep(1)  # be gentle with API
                musicbrainz_release_id = await musicbrainz_api.get_release_by_discogs_url(discogs_release_id)
                if musicbrainz_release_id:
                    album, albumrelease = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(
                        musicbrainz_release_id, discogs_release_id
                    )
                    if albumrelease:
                        await self._link_release_to_collection(
                            collection.collection_uuid,
                            album,
                            albumrelease,
                            fmt="vinyl"
                        )
                        matched_releases.append({
                            "discogs_id": discogs_release_id,
                            "musicbrainz_id": musicbrainz_release_id,
                        })
                        logger.info(f"linked {musicbrainz_release_id} to {discogs_release_id}")
                        continue

                # Fallback: match by artist/title
                artistname = release_info.get("artist")
                title = release_info.get("title")
                if not artistname or not title:
                    discogs_release = discogs_api.get_full_release_details(discogs_release_id, token, secret)
                    if discogs_release:
                        artistname = discogs_release.get("artists", [{}])[0].get("name")
                        title = discogs_release.get("title")
                    else:
                        unmatched_releases.append(release_info)
                        continue

                artistname = re.sub(r'\s*\(\d+\)\s*$', '', artistname)
                new_id = await musicbrainz_api.get_first_release_id_by_artist_and_album(artistname, title)

                if new_id:
                    album, albumrelease = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(
                        new_id, discogs_release_id, True
                    )

                    if albumrelease:
                        if albumrelease.discogs_release_id != discogs_release_id:
                            # clone with new Discogs link
                            new_albumrelease = await musicbrainz_service.clone_album_release_with_links(
                                albumrelease.album_release_uuid, discogs_release_id
                            )
                            await self._link_release_to_collection(
                                collection.collection_uuid,
                                new_albumrelease.album,
                                new_albumrelease,
                                fmt="vinyl"
                            )
                        else:
                            await self._link_release_to_collection(
                                collection.collection_uuid,
                                album,
                                albumrelease,
                                fmt="vinyl"
                            )

                        matched_releases.append({
                            "discogs_id": discogs_release_id,
                            "musicbrainz_id": new_id,
                        })
                        continue

                # Final fallback: Discogs only
                album, albumrelease = await discogs_service.get_or_create_album_from_release(
                    discogs_release_id, token, secret
                )
                if albumrelease:
                    await self._link_release_to_collection(
                        collection.collection_uuid,
                        album,
                        albumrelease,
                        fmt="vinyl"
                    )
                    logger.info(f"✅ Linked via Discogs only {discogs_release_id}")
                else:
                    logger.error(f"❌ Error processing release {discogs_release_id}: No albumrelease returned")
                    unmatched_releases.append(release_info)

            except Exception as e:
                logger.error(f"❌ Error processing release {discogs_release_id}: {e}")
                unmatched_releases.append(release_info)
                await session.rollback()

        logger.info(f"\nSummary: Matched {len(matched_releases)} / {len(new_releases)}")
        return {"matched": matched_releases, "unmatched": unmatched_releases}

    async def _resolve_album_via_mb(self, artist: str, album: str):
        # Use MB search API to find release
        release_id = await self.musicbrainz_service.api.get_first_release_id_by_artist_and_album(artist, album)
        return release_id

    def _get_file_format_and_quality(self, meta, ext: str) -> tuple[str | None, str | None]:
        fmt, quality = None, None

        if ext == ".flac":
            fmt = "FLAC"
            # FLAC is lossless, but we can add resolution
            bits = getattr(meta.info, "bits_per_sample", None)
            rate = getattr(meta.info, "sample_rate", None)
            if bits and rate:
                quality = f"{bits}-bit / {rate // 1000}kHz"
            else:
                quality = "Lossless"

        elif ext == ".mp3":
            fmt = "MP3"
            br = getattr(meta.info, "bitrate", None)
            if br:
                quality = f"{br // 1000} kbps"

        elif ext == ".ogg":
            fmt = "OGG"
            br = getattr(meta.info, "bitrate", None)
            if br:
                quality = f"{br // 1000} kbps"

        elif ext == ".m4a":
            fmt = "M4A"
            br = getattr(meta.info, "bitrate", None)
            if br:
                quality = f"{br // 1000} kbps"

        return fmt, quality


    async def scan_directory(
            self,
            collection_id: UUID | None,
            user_uuid: UUID,
            music_dir: str = settings.MUSIC_DIR,
            include_extensions: tuple[str] = (".flac", ".mp3", ".ogg", ".m4a"),
            limit: int = None,
            overwrite: bool = False,  # 🔥 new flag
    ):
        """
        Walk through a directory, extract tags, resolve with MusicBrainz,
        and persist CollectionTrack rows.

        🔴 Guaranteed stop after `limit` files (success, skip, or fail).
        """

        def normalize(s: str | None) -> str | None:
            if not s:
                return None
            return re.sub(r"\s+", " ", s.strip().lower())

        # Ensure collection exists
        if not collection_id:
            collection = await self.get_or_create_collection(user_uuid, "Local Music Collection")
            collection_id = collection.collection_uuid

            # Ensure collection exists
            if not collection_id:
                collection = await self.get_or_create_collection(user_uuid, "Local Music Collection")
                collection_id = collection.collection_uuid

            if overwrite:
                # Wipe collection before scanning
                await self.db.execute(
                    delete(CollectionTrack).where(CollectionTrack.collection_uuid == collection_id)
                )
                await self.db.execute(
                    delete(CollectionAlbumReleaseBridge).where(
                        CollectionAlbumReleaseBridge.collection_uuid == collection_id)
                )
                await self.db.execute(
                    delete(CollectionAlbumBridge).where(CollectionAlbumBridge.collection_uuid == collection_id)
                )
                await self.db.execute(
                    delete(CollectionAlbumFormat).where(CollectionAlbumFormat.collection_uuid == collection_id)
                )
                await self.db.commit()
                logger.info(f"Overwriting existing collection {collection_id} – flushed tracks/releases/albums.")

        attempts = 0
        successes = 0
        release_cache: dict[tuple[str, str], str] = {}  # (artist, album) -> release_id


        for root, _, files in os.walk(music_dir):
            dir_successes = 0
            dir_attempts = 0
            current_artist, current_album = None, None

            for fname in files:
                if not fname.lower().endswith(include_extensions):
                    continue

                # 🔴 Count this file immediately
                attempts += 1
                dir_attempts += 1
                if limit:
                    if attempts > limit:
                        logger.info(
                            f"Stopping after {limit} files "
                            f"({successes} successes, {attempts - successes} failures/skips)."
                        )
                        return

                path = os.path.join(root, fname)
                try:
                    meta = MutagenFile(path)
                    if not meta or not meta.tags:
                        continue
                    tags = {k.lower(): v for k, v in meta.tags.items()}

                    artist = tags.get("artist", [None])[0]
                    album = tags.get("album", [None])[0]
                    title = tags.get("title", [None])[0]
                    mb_albumid = tags.get("musicbrainz_albumid", [None])[0]
                    mb_trackid = tags.get("musicbrainz_trackid", [None])[0]

                    if not artist or not album or not title:
                        continue

                    current_artist, current_album = artist, album

                    # 🔒 Normalize cache key
                    cache_key = (normalize(artist), normalize(album))

                    # Resolve release_id
                    release_id: str | None = mb_albumid
                    if not release_id:
                        if cache_key in release_cache:
                            release_id = release_cache[cache_key]
                        else:
                            release_id = await self._resolve_album_via_mb(artist, album)
                            if not release_id:
                                continue
                            release_cache[cache_key] = release_id

                    # 1. get or create album + release (+tracks/versions)
                    album_obj, album_release = (
                        await self.musicbrainz_service.get_or_create_album_from_musicbrainz_release(
                            str(release_id)
                        )
                    )

                    # 2. get or create track_version
                    track_version = await self.musicbrainz_service.get_or_create_track_version(
                        str(release_id),
                        title,
                        mb_trackid,
                    )
                    if not track_version:
                        continue

                    # 3. skip if already in collection
                    result = await self.db.execute(
                        select(CollectionTrack).where(
                            CollectionTrack.collection_uuid == collection_id,
                            CollectionTrack.track_version_uuid == track_version.track_version_uuid,
                        )
                    )
                    if result.scalar_one_or_none():
                        continue

                    # 4. persist new CollectionTrack
                    ext = os.path.splitext(fname)[1].lower()
                    fmt, quality = self._get_file_format_and_quality(meta, ext)

                    ct = CollectionTrack(
                        collection_uuid=collection_id,
                        track_version_uuid=track_version.track_version_uuid,
                        path=path,
                        format=fmt,
                        quality=quality,
                    )
                    self.db.add(ct)


                    album_uuid = album_obj.album_uuid
                    album_release_uuid = album_release.album_release_uuid

                    # CollectionAlbumBridge
                    stmt = insert(CollectionAlbumBridge).values(
                        album_uuid=album_uuid,
                        collection_uuid=collection_id
                    ).on_conflict_do_nothing()
                    await self.db.execute(stmt)

                    # CollectionAlbumReleaseBridge
                    stmt = insert(CollectionAlbumReleaseBridge).values(
                        album_release_uuid=album_release_uuid,
                        collection_uuid=collection_id
                    ).on_conflict_do_nothing()
                    await self.db.execute(stmt)

                    # CollectionAlbumFormat (mark digital owned)
                    stmt = insert(CollectionAlbumFormat).values(
                        collection_uuid=collection_id,
                        album_uuid=album_uuid,
                        format="digital",
                        status="owned"
                    ).on_conflict_do_nothing()
                    await self.db.execute(stmt)

                    # 🔴 commit each addition
                    await self.db.commit()
                    dir_successes += 1
                    successes += 1


                except Exception as e:
                    logger.error(f"❌ Error processing {path}: {e}")

            if dir_attempts > 0 and current_artist and current_album:
                logger.info(
                    f"Added {current_artist}, {current_album} "
                    f"{dir_successes}/{dir_attempts} tracks"
                )

        logger.info(
            f"Scan finished: {attempts} files processed "
            f"({successes} successes, {attempts - successes} failures/skips)."
        )





