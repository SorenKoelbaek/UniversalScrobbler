
import os
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies.database import get_async_session
from services.musicbrainz_service import MusicBrainzService
from dependencies.musicbrainz_api import MusicBrainzAPI
# Add the parent directory (api folder) to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.dirname(script_dir)
sys.path.append(api_dir)
from sqlmodel import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Album, Artist, Track, Tag, Genre, AlbumTagBridge, ArtistTagBridge
import re
from typing import Optional
import asyncio
import tarfile
import gzip
import json
from datetime import datetime
from config import settings
import logging
logger = logging.getLogger(__name__)


class ImportCollection:
    def __init__(self, db: AsyncSession, ):
            self.db = db
            self.musicbrainz_api = MusicBrainzAPI()
            self.musicbrainz_service = MusicBrainzService(self.db, self.musicbrainz_api)

    async def import_artist_from_musicbrainz(self, data: dict) -> Artist:
        name = data["name"]
        musicbrainz_artist_id = data["id"]

        # Try to find or create the artist
        artist = await self.musicbrainz_service.get_or_create_artist_by_name(name, musicbrainz_artist_id)

        # Set quality and discogs ID if the artist was just created
        if not artist.quality:
            artist.quality = "normal"

        if not artist.discogs_artist_id:
            # Look for a discogs relation
            for rel in data.get("relations", []):
                if rel.get("type") == "discogs" and "url" in rel:
                    discogs_url = rel["url"].get("resource")
                    if discogs_url and "discogs.com/artist/" in discogs_url:
                        try:
                            artist.discogs_artist_id = int(discogs_url.strip("/").split("/")[-1])
                        except ValueError:
                            pass  # malformed ID, skip

        # Add tags, if present
        for tag in data.get("tags", []):
            tag_name = self.normalize_tag_name(tag["name"])
            tag_obj = await self.musicbrainz_service.get_or_create_tag(tag_name)
            result = await self.db.execute(
                select(ArtistTagBridge).where(
                    ArtistTagBridge.artist_uuid == artist.artist_uuid,
                    ArtistTagBridge.tag_uuid == tag_obj.tag_uuid,
                )
            )
            existing = result.scalar_one_or_none()
            if not existing:
                self.db.add(ArtistTagBridge(
                    artist_uuid=artist.artist_uuid,
                    tag_uuid=tag_obj.tag_uuid,
                    count=tag.get("count", 0)
                ))

        return artist

    async def import_album_from_release_group(self, release_group_data: dict) -> Album:
        return await self.musicbrainz_service.get_or_create_album_from_release_group_simple(release_group_data)

    def extract_discogs_release_id(self, release_data: dict) -> Optional[int]:
        for rel in release_data.get("relations", []):
            if rel.get("type") == "discogs" and rel.get("target-type") == "url":
                url = rel.get("url", {}).get("resource", "")
                match = re.search(r"/release/(\d+)", url)
                if match:
                    return int(match.group(1))
        return None

    async def create_album_release_from_release_data(self, release_data: dict):
        release_group_data = release_data["release-group"]

        album = await self.musicbrainz_service.get_or_create_album_from_release_group_simple(release_group_data)
        discogs_release_id = self.extract_discogs_release_id(release_data)
        album_release = await self.musicbrainz_service.create_album_release_simple(album, release_data, discogs_release_id)
        # Now just reuse the existing method
        return album_release

    def normalize_tag_name(self, name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[\.\-_]", " ", name)  # replace punctuation with spaces
        name = re.sub(r"\s+", " ", name)  # collapse multiple spaces
        name = name.replace("&", "and")  # common synonym
        return name.strip()

    async def import_data(self, folder_name: str):
        path = f"scripts/{folder_name}.tar.xz"
        if not os.path.exists(path):
            raise FileNotFoundError(f"Expected file {path} not found")

        with tarfile.open(path, "r:xz") as tar:
            for member in tar:
                if member.name.endswith(f"mbdump/{folder_name}"):
                    start = datetime.now()
                    f = tar.extractfile(member)
                    if not f:
                        raise RuntimeError(f"Could not extract member {member.name} from archive")

                    for i, line in enumerate(f):
                        data = json.loads(line)
                        if folder_name == "artist":
                            await self.import_artist_from_musicbrainz(data)
                        elif folder_name == "release-group":
                            await self.import_album_from_release_group(data)
                        elif folder_name == "release":
                            await self.create_album_release_from_release_data(data)
                        else:
                            raise NotImplementedError(f"Unknown folder name: {folder_name}")

                        await self.db.commit()

                    break
            else:
                raise ValueError(f"No matching mbdump/{folder_name} entry found in tar")

if __name__ == "__main__":
    import argparse
    import asyncio
    from dependencies.database import get_engine, get_sessionmaker

    async def main():
        parser = argparse.ArgumentParser(description="Import MusicBrainz data")
        parser.add_argument(
            "folder",
            choices=["artist", "release-group", "release"],
            help="Which MusicBrainz entity to import",
        )
        args = parser.parse_args()

        engine = get_engine()
        async_sessionmaker = get_sessionmaker(engine)

        async with async_sessionmaker() as session:
            importer = ImportCollection(session)
            await importer.import_data(args.folder)
            print(f"✅ Imported {args.folder} successfully.")

    asyncio.run(main())