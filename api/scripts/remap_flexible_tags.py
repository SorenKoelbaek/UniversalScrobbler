# Fix Python paths
import os
import sys
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
from typing import List
from sqlmodel import SQLModel, Field, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies.database import get_async_session
from models.sqlmodels import (
    FlexibleTagMapping,
    AlbumTagBridge,
    ArtistTagBridge,
    AlbumReleaseTagBridge,
    TrackVersionTagBridge,
)

async def migrate_album_tag_bridge(session: AsyncSession):
    print("Processing AlbumTagBridge...")
    stmt = (
        select(
            AlbumTagBridge.album_uuid,
            FlexibleTagMapping.to_tag_uuid,
            AlbumTagBridge.count,
            FlexibleTagMapping.from_tag_uuid,
        )
        .join(FlexibleTagMapping, AlbumTagBridge.tag_uuid == FlexibleTagMapping.from_tag_uuid)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        print("No mappings found for AlbumTagBridge.")
        return

    new_rows = [
        {
            "album_uuid": album_uuid,
            "tag_uuid": to_tag_uuid,
            "count": count
        }
        for album_uuid, to_tag_uuid, count, _ in rows
    ]

    # Insert new mappings
    for i in range(0, len(new_rows), 1000):
        chunk = new_rows[i:i+1000]
        await session.execute(
            insert(AlbumTagBridge)
            .values(chunk)
            .on_conflict_do_nothing()
        )
        await session.commit()

    # Delete old mappings
    from_tag_uuids = set(row[3] for row in rows)
    await session.execute(
        AlbumTagBridge.__table__.delete().where(AlbumTagBridge.tag_uuid.in_(from_tag_uuids))
    )
    await session.commit()
    print(f"✅ AlbumTagBridge migrated: {len(new_rows)} rows inserted.")

async def migrate_artist_tag_bridge(session: AsyncSession):
    print("Processing ArtistTagBridge...")
    stmt = (
        select(
            ArtistTagBridge.artist_uuid,
            FlexibleTagMapping.to_tag_uuid,
            ArtistTagBridge.count,
            FlexibleTagMapping.from_tag_uuid,
        )
        .join(FlexibleTagMapping, ArtistTagBridge.tag_uuid == FlexibleTagMapping.from_tag_uuid)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        print("No mappings found for ArtistTagBridge.")
        return

    new_rows = [
        {
            "artist_uuid": artist_uuid,
            "tag_uuid": to_tag_uuid,
            "count": count
        }
        for artist_uuid, to_tag_uuid, count, _ in rows
    ]

    for i in range(0, len(new_rows), 1000):
        chunk = new_rows[i:i+1000]
        await session.execute(
            insert(ArtistTagBridge)
            .values(chunk)
            .on_conflict_do_nothing()
        )
        await session.commit()

    from_tag_uuids = set(row[3] for row in rows)
    await session.execute(
        ArtistTagBridge.__table__.delete().where(ArtistTagBridge.tag_uuid.in_(from_tag_uuids))
    )
    await session.commit()
    print(f"✅ ArtistTagBridge migrated: {len(new_rows)} rows inserted.")

async def migrate_album_release_tag_bridge(session: AsyncSession):
    print("Processing AlbumReleaseTagBridge...")
    stmt = (
        select(
            AlbumReleaseTagBridge.album_release_uuid,
            FlexibleTagMapping.to_tag_uuid,
            AlbumReleaseTagBridge.count,
            FlexibleTagMapping.from_tag_uuid,
        )
        .join(FlexibleTagMapping, AlbumReleaseTagBridge.tag_uuid == FlexibleTagMapping.from_tag_uuid)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        print("No mappings found for AlbumReleaseTagBridge.")
        return

    new_rows = [
        {
            "album_release_uuid": album_release_uuid,
            "tag_uuid": to_tag_uuid,
            "count": count
        }
        for album_release_uuid, to_tag_uuid, count, _ in rows
    ]

    for i in range(0, len(new_rows), 1000):
        chunk = new_rows[i:i+1000]
        await session.execute(
            insert(AlbumReleaseTagBridge)
            .values(chunk)
            .on_conflict_do_nothing()
        )
        await session.commit()

    from_tag_uuids = set(row[3] for row in rows)
    await session.execute(
        AlbumReleaseTagBridge.__table__.delete().where(AlbumReleaseTagBridge.tag_uuid.in_(from_tag_uuids))
    )
    await session.commit()
    print(f"✅ AlbumReleaseTagBridge migrated: {len(new_rows)} rows inserted.")

async def migrate_track_version_tag_bridge(session: AsyncSession):
    print("Processing TrackVersionTagBridge...")
    stmt = (
        select(
            TrackVersionTagBridge.track_version_uuid,
            FlexibleTagMapping.to_tag_uuid,
            TrackVersionTagBridge.count,
            FlexibleTagMapping.from_tag_uuid,
        )
        .join(FlexibleTagMapping, TrackVersionTagBridge.tag_uuid == FlexibleTagMapping.from_tag_uuid)
    )
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        print("No mappings found for TrackVersionTagBridge.")
        return

    new_rows = [
        {
            "track_version_uuid": track_version_uuid,
            "tag_uuid": to_tag_uuid,
            "count": count
        }
        for track_version_uuid, to_tag_uuid, count, _ in rows
    ]

    for i in range(0, len(new_rows), 1000):
        chunk = new_rows[i:i+1000]
        await session.execute(
            insert(TrackVersionTagBridge)
            .values(chunk)
            .on_conflict_do_nothing()
        )
        await session.commit()

    from_tag_uuids = set(row[3] for row in rows)
    await session.execute(
        TrackVersionTagBridge.__table__.delete().where(TrackVersionTagBridge.tag_uuid.in_(from_tag_uuids))
    )
    await session.commit()
    print(f"✅ TrackVersionTagBridge migrated: {len(new_rows)} rows inserted.")

async def main():
    async for session in get_async_session():
        await migrate_album_tag_bridge(session)
        await migrate_artist_tag_bridge(session)
        await migrate_album_release_tag_bridge(session)
        await migrate_track_version_tag_bridge(session)

if __name__ == "__main__":
    asyncio.run(main())
