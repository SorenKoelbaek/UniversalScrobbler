# scripts/generate_flexible_tag_mappings.py

import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession

import asyncio
from sqlalchemy import text

# Fix Python paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlmodel import SQLModel, Field
from dependencies.database import get_async_session

# FlexibleTagMapping model
async def build_flexible_mappings(session: AsyncSession):
    print("✅ Loading tags...")

    # Load all tags into a cache
    result = await session.execute(
        text("SELECT tag_uuid, name FROM tag")
    )
    rows = result.all()
    tag_name_to_uuid = {name.strip(): uuid for uuid, name in rows}
    tag_names = set(tag_name_to_uuid.keys())

    print(f"✅ Loaded {len(tag_names)} tags into memory.")

    # Now find "complex" tags
    result = await session.execute(
        text("""
            SELECT tag_uuid, name
            FROM tag
            WHERE name LIKE '%;%' OR name LIKE '%/%' OR name LIKE '%:%'
        """)
    )
    complex_tags = result.all()

    flexible_mappings = []

    for from_uuid, name in complex_tags:
        # Split by known delimiters
        parts = re.split(r";|/|:", name)
        parts = [p.strip() for p in parts if p.strip()]

        for part in parts:
            if part in tag_name_to_uuid:
                to_uuid = tag_name_to_uuid[part]
                flexible_mappings.append({
                    "from_tag_uuid": str(from_uuid),
                    "to_tag_uuid": str(to_uuid)
                })

    print(f"✅ Found {len(flexible_mappings)} flexible mappings.")

    # Insert into table properly
    if flexible_mappings:
        # Insert in batches
        for chunk in [flexible_mappings[i:i + 1000] for i in range(0, len(flexible_mappings), 1000)]:
            values_sql = ", ".join(
                f"('{row['from_tag_uuid']}', '{row['to_tag_uuid']}')" for row in chunk
            )
            query = text(f"""
                INSERT INTO flexible_tag_mapping (from_tag_uuid, to_tag_uuid)
                VALUES {values_sql}
                ON CONFLICT DO NOTHING
            """)
            await session.execute(query)
            await session.commit()

async def main():
    async for session in get_async_session():
        await build_flexible_mappings(session)

if __name__ == "__main__":
    import re
    asyncio.run(main())
