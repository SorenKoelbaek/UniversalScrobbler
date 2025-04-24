
from sqlalchemy.orm import selectinload

from models.sqlmodels import Collection, Album
from models.appmodels import CollectionSimple, CollectionSimpleRead
from uuid import UUID
from fastapi import HTTPException
import csv
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

import asyncio
import re
from dependencies.musicbrainz_api import MusicBrainzAPI
from dependencies.discogs_api import DiscogsAPI
from models.sqlmodels import DiscogsToken, AlbumRelease
from services.musicbrainz_service import MusicBrainzService
from services.discogs_service import DiscogsService
from config import settings
import logging
logger = logging.getLogger(__name__)

discogs_api = DiscogsAPI()

class CollectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

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
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Collection).where(Collection.user_uuid == collection_id)
        .options(
            selectinload(Collection.albums).selectinload(Album.artists),  # Eager load albums and their artists
            selectinload(Collection.albums).selectinload(Album.tracks),  # Eager load albums and their tracks
            selectinload(Collection.album_releases).selectinload(AlbumRelease.artists)
            # Eager load album releases and their artists
        ))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionSimpleRead.model_validate(collection)  # Use model_validate instead of parse_obj

    async def get_primary_collection(self, user_uuid: UUID) -> CollectionSimpleRead:
        result = await self.db.execute(select(Collection).where(Collection.user_uuid == user_uuid)
        .options(
            selectinload(Collection.albums).selectinload(Album.artists),  # Eager load albums and their artists
            selectinload(Collection.albums).selectinload(Album.tracks),  # Eager load albums and their tracks
            selectinload(Collection.album_releases).selectinload(AlbumRelease.artists)
            # Eager load album releases and their artists
        ))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Album not found")
        return CollectionSimpleRead.model_validate(collection)  # Use model_validate instead of parse_obj

    async def get_collection_simple(self, collection_id: UUID) -> CollectionSimple:
        """Retrieve a single album based on UUID."""
        result = await self.db.execute(select(Collection).where(Collection.collection_uuid == collection_id).options(
            selectinload(Collection.albums), selectinload(Collection.album_releases)))
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
        result = await session.exec(select(DiscogsToken).where(DiscogsToken.user_uuid == user_uuid))
        auth = result.first()
        token = auth.access_token
        secret = auth.access_token_secret

        collection = await self.get_or_create_collection(user_uuid, "Discogs main collection")
        collection_to_process = (
            await self.read_collection_from_csv(csv_file_path)
            if csv_file_path else
            discogs_api.get_collection(token, secret)
        )

        existing_release_ids = {r.discogs_release_id for r in collection.album_releases}

        new_releases = [r for r in collection_to_process if r["discogs_release_id"] not in existing_release_ids]
        logger.info(f"Found {len(new_releases)} new releases to process")
        for index, release_info in enumerate(new_releases):

            discogs_release_id = release_info["discogs_release_id"]
            logger.info(f"Processing {index + 1}/{len(new_releases)}: Discogs ID {discogs_release_id}")
            try:
                result = await session.exec(
                    select(AlbumRelease).where(AlbumRelease.discogs_release_id == discogs_release_id)
                )
                albumrelease = result.first()

                if albumrelease:
                    await musicbrainz_service.link_release_to_collection(
                        albumrelease.album_release_uuid, collection.collection_uuid
                    )
                    print("✅ Linked existing album release")
                    await session.commit()
                    continue

                await asyncio.sleep(1)
                musicbrainz_release_id = await musicbrainz_api.get_release_by_discogs_url(discogs_release_id)
                if musicbrainz_release_id:
                    album, albumrelease = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(
                        musicbrainz_release_id, discogs_release_id
                    )

                    if albumrelease:
                        await musicbrainz_service.link_release_to_collection(
                            albumrelease.album_release_uuid, collection.collection_uuid
                        )
                        matched_releases.append({
                            "discogs_id": discogs_release_id,
                            "musicbrainz_id": musicbrainz_release_id,
                        })
                        print(f"linked {musicbrainz_release_id} to {discogs_release_id}")
                        await session.commit()
                        continue

                artistname = release_info.get("artist")
                title = release_info.get("title")
                if not artistname or not title:
                    discogs_release = discogs_api.get_full_release_details(discogs_release_id, token, secret)
                    if discogs_release:
                        artistname = discogs_release.get("artists", [{}])[0].get("name")
                        title = discogs_release.get("title")
                    else:
                        unmatched_releases.append(release_info)
                        await session.rollback()
                        continue
                artistname = re.sub(r'\s*\(\d+\)\s*$', '', artistname)
                new_id = await musicbrainz_api.get_first_release_id_by_artist_and_album(artistname, title)

                if new_id:
                    album, albumrelease = await musicbrainz_service.get_or_create_album_from_musicbrainz_release(
                        new_id, discogs_release_id, True
                    )

                    if albumrelease:
                        if albumrelease.discogs_release_id != discogs_release_id:
                            albumbumrelease = await musicbrainz_service.clone_album_release_with_links(
                                albumrelease.album_release_uuid, discogs_release_id)
                            await musicbrainz_service.link_release_to_collection(
                                albumbumrelease.album_release_uuid, collection.collection_uuid
                            )
                            matched_releases.append({
                                "discogs_id": discogs_release_id,
                                "musicbrainz_id": new_id,
                            })
                        else:
                            await musicbrainz_service.link_release_to_collection(
                                albumrelease.album_release_uuid, collection.collection_uuid
                            )
                            matched_releases.append({
                                "discogs_id": discogs_release_id,
                                "musicbrainz_id": new_id,
                            })

                        await session.commit()
                        continue

                album, albumrelease = await discogs_service.get_or_create_album_from_release(
                    discogs_release_id, token, secret
                )
                if albumrelease:
                    await musicbrainz_service.link_release_to_collection(
                        albumrelease.album_release_uuid, collection.collection_uuid
                    )
                    await session.commit()
                else:
                    print(f"❌ Error processing release {discogs_release_id}: No albumrelease returned")
                    await session.rollback()

            except Exception as e:
                print(f"❌ Error processing release {discogs_release_id}: {e}")
                await session.rollback()

        print(f"\nSummary:")
        print(f"Matched {len(matched_releases)} / {len(new_releases)}")
        print(unmatched_releases)
        return {"matched": matched_releases, "unmatched": unmatched_releases}
