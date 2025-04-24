
import os
import sys
from collections import defaultdict

from sqlalchemy import func

# 🔧 Add project root to sys.path for relative imports to work
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

from sqlalchemy import text

if project_root not in sys.path:
    sys.path.insert(0, project_root)
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies.database import get_async_session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from services.musicbrainz_service import MusicBrainzService
from dependencies.musicbrainz_api import MusicBrainzAPI
# Add the parent directory (api folder) to the Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
api_dir = os.path.dirname(script_dir)
sys.path.append(api_dir)
from sqlmodel import select, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import AlbumType, AlbumTypeBridge, Album, Artist, Track, Tag, Genre, AlbumTagBridge, \
    ArtistTagBridge, AlbumRelease, TrackArtistBridge, TrackVersion, TrackAlbumBridge, PlaybackHistory
import re
from typing import Optional, Dict
import asyncio
from uuid import UUID
import tarfile
import gzip
import json
from datetime import datetime
from config import settings
import logging
logger = logging.getLogger(__name__)
from sqlalchemy import tuple_

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

    ALBUM_TYPE_DEFINITIONS = {
        "Album": "An album, perhaps better defined as a \"Long Play\" (LP) release, generally consists of previously unreleased material (unless this type is combined with secondary types which change that, such as \"Compilation\").",
        "Single": "A single has different definitions depending on the market it is released for...",
        "EP": "An EP is a so-called \"Extended Play\" release and often contains the letters EP in the title...",
        "Broadcast": "An episodic release that was originally broadcast via radio, television, or the Internet, including podcasts.",
        "Other": "Any release that does not fit or can't decisively be placed in any of the categories above.",
        "Compilation": "A compilation covers the following types of releases: a collection of recordings from various old sources...",
        "Soundtrack": "A soundtrack is the musical score to a movie, TV series, stage show, video game, or other medium.",
        "Spokenword": "Non-music spoken word releases.",
        "Interview": "An interview release contains an interview, generally with an artist.",
        "Audiobook": "An audiobook is a book read by a narrator without music.",
        "Audio drama": "An audio drama is an audio-only performance of a play...",
        "Live": "A release that was recorded live.",
        "Remix": "A release that primarily contains remixed material.",
        "DJ-mix": "A DJ-mix is a sequence of several recordings played one after the other...",
        "Mixtape/Street": "Promotional in nature (but not necessarily free), mixtapes and street albums are often released by artists...",
        "Demo": "A demo is typically distributed for limited circulation or reference use...",
        "Field recording": "A release mostly consisting of field recordings (such as nature sounds or city/industrial noise)."
    }

    async def preload_album_type_cache(self) -> Dict[str, UUID]:
        result = await self.db.execute(select(AlbumType.name, AlbumType.album_type_uuid))
        existing_types = {name: uuid for name, uuid in result.all()}

        for name, description in self.ALBUM_TYPE_DEFINITIONS.items():
            if name not in existing_types:
                new_type = AlbumType(name=name, description=description)
                self.db.add(new_type)
                await self.db.flush()
                existing_types[name] = new_type.album_type_uuid

        await self.db.commit()

        result = await self.db.execute(select(AlbumType.name, AlbumType.album_type_uuid))
        existing_types = {name: uuid for name, uuid in result.all()}

        return existing_types

    async def attach_album_types(self, data: dict, album_uuid: UUID):
        # Primary type
        primary_name = data.get("primary-type")
        type_uuids = []

        if primary_name:
            primary_uuid = self.album_type_cache.get(primary_name)
            if primary_uuid:
                type_uuids.append((primary_uuid, True))  # mark as primary

        # Secondary types
        for sec_type in data.get("secondary-types", []):
            sec_uuid = self.album_type_cache.get(sec_type)
            if sec_uuid:
                type_uuids.append((sec_uuid, False))

        # Add bridge entries
        for type_uuid, is_primary in type_uuids:
            bridge = AlbumTypeBridge(album_uuid=album_uuid, album_type_uuid=type_uuid, primary=is_primary)
            self.db.add(bridge)

    def normalize_tag_name(self, name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[\.\-_]", " ", name)  # replace punctuation with spaces
        name = re.sub(r"\s+", " ", name)  # collapse multiple spaces
        name = name.replace("&", "and")  # common synonym
        return name.strip()

    BATCH_SIZE = 1000

    async def deduplicate_tracks(self):
        print("🔍 Identifying duplicate tracks (same name & artist)...")

        # Step 1: get all duplicate (artist_uuid, name) combinations with more than one track
        duplicates_query = text("""
            SELECT artist_uuid, name
            FROM track_artist_bridge
            JOIN track USING(track_uuid)
            GROUP BY artist_uuid, name
            HAVING COUNT(track_uuid) > 1
        """)

        result = await self.db.execute(duplicates_query)
        duplicate_keys = result.fetchall()
        total_duplicates = len(duplicate_keys)
        print(f"🚨 Found {total_duplicates} duplicated track groups.")

        # Step 2: batch process
        for i in range(0, total_duplicates, self.BATCH_SIZE):
            batch = duplicate_keys[i:i + self.BATCH_SIZE]
            print(f"🔁 Processing batch {i}–{i + len(batch)}...")

            for artist_uuid, name in batch:
                track_query = (
                    select(Track)
                    .join(TrackArtistBridge, Track.track_uuid == TrackArtistBridge.track_uuid)
                    .where(Track.name == name, TrackArtistBridge.artist_uuid == artist_uuid)
                )
                result = await self.db.execute(track_query)
                tracks = result.scalars().all()

                if len(tracks) < 2:
                    continue

                # Select one canonical track to keep
                tracks.sort(key=lambda t: str(t.track_uuid))  # stable choice
                canonical = tracks[0]
                to_remove = tracks[1:]

                for duplicate in to_remove:
                    # Update TrackVersion.track_uuid
                    await self.db.execute(
                        text("""
                            UPDATE track_version
                            SET track_uuid = :new_uuid
                            WHERE track_uuid = :old_uuid
                        """),
                        {"new_uuid": str(canonical.track_uuid), "old_uuid": str(duplicate.track_uuid)}
                    )

                    # Update PlaybackHistory
                    await self.db.execute(
                        text("""
                            UPDATE playback_history
                            SET track_uuid = :new_uuid
                            WHERE track_uuid = :old_uuid
                        """),
                        {"new_uuid": str(canonical.track_uuid), "old_uuid": str(duplicate.track_uuid)}
                    )

                    # Update TrackAlbumBridge, avoiding duplicates
                    await self.db.execute(
                        text("""
                            INSERT INTO track_album_bridge (track_uuid, album_uuid, track_number)
                            SELECT :new_uuid, album_uuid, track_number
                            FROM track_album_bridge
                            WHERE track_uuid = :old_uuid
                            ON CONFLICT DO NOTHING
                        """),
                        {"new_uuid": str(canonical.track_uuid), "old_uuid": str(duplicate.track_uuid)}
                    )

                    # Update TrackArtistBridge, avoiding duplicates
                    await self.db.execute(
                        text("""
                            INSERT INTO track_artist_bridge (track_uuid, artist_uuid)
                            SELECT :new_uuid, artist_uuid
                            FROM track_artist_bridge
                            WHERE track_uuid = :old_uuid
                            ON CONFLICT DO NOTHING
                        """),
                        {"new_uuid": str(canonical.track_uuid), "old_uuid": str(duplicate.track_uuid)}
                    )

                    # Remove bridge entries for duplicate
                    await self.db.execute(
                        delete(TrackAlbumBridge).where(TrackAlbumBridge.track_uuid == duplicate.track_uuid)
                    )
                    await self.db.execute(
                        delete(TrackArtistBridge).where(TrackArtistBridge.track_uuid == duplicate.track_uuid)
                    )

                    # Finally, delete the duplicate track
                    await self.db.execute(
                        delete(Track).where(Track.track_uuid == duplicate.track_uuid)
                    )

            await self.db.commit()
            print(f"✅ Committed deduplication batch {i}–{i + len(batch)}")

        print("🎉 Deduplication complete.")

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

        result = await self.db.execute(select(Album.musicbrainz_release_group_id))
        self.existing_album_release_ids = set(row[0] for row in result.all() if row[0])

        self.album_type_cache = await self.preload_album_type_cache()

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
                            musicbrainz_release_group_id = data.get("id")
                            if musicbrainz_release_group_id in self.existing_album_release_ids:
                                album_uuid = self.album_cache.get(musicbrainz_release_group_id)
                                await self.attach_album_types(data, album_uuid)
                            else:
                               album = await self.import_album_from_release_group(data)
                               await self.attach_album_types(data, album.album_uuid)
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
            if args.folder == "track":
                await importer.deduplicate_tracks()
            else:
                await importer.import_data(args.folder)
            print(f"✅ Imported {args.folder} successfully.")

    asyncio.run(main())
