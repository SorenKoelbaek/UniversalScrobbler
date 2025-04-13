
import os
import sys

# 🔧 Add project root to sys.path for relative imports to work
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
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
from models.sqlmodels import Album, Artist, Track, Tag, Genre, AlbumTagBridge, ArtistTagBridge, AlbumRelease
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
            self.musicbrainz_service: Optional[MusicBrainzService] = None

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
        media = release_data.get("media", [])
        media_tracks = []
        recordings_data = []

        for disc in media:
            for track in disc.get("tracks", []):
                media_tracks.append(track)
                if "recording" in track:
                    recording = track["recording"].copy()
                    recording["recording_id"] = recording["id"]
                    recordings_data.append(recording)

        artists = await self.musicbrainz_service.create_tracks_and_versions_simple(
            album=album,
            album_release=album_release,
            media_tracks=media_tracks,
            recordings_data=recordings_data,
        )
        # Now just reuse the existing method
        return artists

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

        # 🔃 Preload all known artists into cache (MBID → UUID)
        result = await self.db.execute(select(Artist.artist_uuid, Artist.musicbrainz_artist_id))
        self.artist_cache = {
            mbid: uuid for uuid, mbid in result.all() if mbid
        }
        result = await self.db.execute(select(Album.album_uuid, Album.musicbrainz_release_group_id))
        self.album_cache = {
            mbid: uuid for uuid, mbid in result.all() if mbid
        }

        result = await self.db.execute(select(Tag.tag_uuid, Tag.name))
        self.tag_cache = {
            self.normalize_tag_name(name): uuid for uuid, name in result.all()
        }

        result = await self.db.execute(select(AlbumRelease.musicbrainz_release_id))
        self.existing_release_ids = set(row[0] for row in result.all() if row[0])


        #after the cache is created, we can create the musicbrainz service
        self.musicbrainz_service = MusicBrainzService(
            self.db,
            self.musicbrainz_api,
            artist_cache=self.artist_cache,
            album_cache=self.album_cache,
            tag_cache=self.tag_cache
        )

        with tarfile.open(path, "r:xz") as tar:
            for member in tar:
                if member.name.endswith(f"mbdump/{folder_name}"):
                    start = datetime.now()
                    f = tar.extractfile(member)
                    if not f:
                        raise RuntimeError(f"Could not extract member {member.name} from archive")

                    for i, line in enumerate(f, start=1):
                        data = json.loads(line)
                        if folder_name == "artist":
                            await self.import_artist_from_musicbrainz(data)
                        elif folder_name == "release-group":
                            await self.import_album_from_release_group(data)
                        elif folder_name == "release":
                            musicbrainz_release_id = data.get("id")
                            if musicbrainz_release_id in self.existing_release_ids:
                                continue  # ✅ Skip already imported release
                            new_artists  = await self.create_album_release_from_release_data(data)
                        else:
                            raise NotImplementedError(f"Unknown folder name: {folder_name}")

                        # ✅ Log every 1000 records
                        if i % 1000 == 0:
                            await self.db.commit()
                            elapsed = (datetime.now() - start).total_seconds()
                            start = datetime.now()
                            print(f"[{folder_name}] Processed {i} records in {elapsed:.2f} seconds")

                    await self.db.commit()
                    break
            else:
                raise ValueError(f"No matching mbdump/{folder_name} entry found in tar")

if __name__ == "__main__":
    import argparse
    import asyncio
    from dependencies.database import get_async_session

    async def main():
        parser = argparse.ArgumentParser(description="Import MusicBrainz data")
        parser.add_argument(
            "folder",
            choices=["artist", "release-group", "release"],
            help="Which MusicBrainz entity to import",
        )
        args = parser.parse_args()

        # ✅ Use your real session dependency properly
        async for session in get_async_session():
            importer = ImportCollection(session)
            await importer.import_data(args.folder)
            print(f"✅ Imported {args.folder} successfully.")

    asyncio.run(main())
