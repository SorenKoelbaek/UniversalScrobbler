import os
import sys
import asyncio
import csv
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, Field
from sqlalchemy import text

# Fix Python paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dependencies.database import get_async_session


async def load_styles_from_csv(session: AsyncSession, path: str):
    styles = []
    mappings = []
    stack = []  # [(level, style_uuid)]

    with open(path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter='\t')

        for idx, row in enumerate(reader, start=2):  # line 2 is first row after header
            name = row.get("style_name")
            if name is None or name.strip() == "":
                print(f"⚠️ Skipping empty or invalid row {idx}: {row}")
                continue

            raw_indent = row.get("indentation", "")
            description = row.get("style_description", "") or ""

            name = name.strip()
            description = description.strip()
            level = raw_indent.count(";")
            style_uuid = str(uuid4())

            # Pop stack to find correct parent
            while stack and stack[-1][0] >= level:
                stack.pop()

            parent_uuid = stack[-1][1] if stack else None

            styles.append({
                "style_uuid": style_uuid,
                "style_name": name,
                "style_description": description,
                "style_parent_uuid": parent_uuid
            })

            for ancestor_level, ancestor_uuid in stack:
                mappings.append({
                    "from_style_uuid": ancestor_uuid,
                    "to_style_uuid": style_uuid
                })

            stack.append((level, style_uuid))

    print(f"✅ Parsed {len(styles)} styles and {len(mappings)} mappings")

    # Insert styles
    for chunk in [styles[i:i + 1000] for i in range(0, len(styles), 1000)]:
        values_sql = ", ".join(
            f"('{s['style_uuid']}', :name_{i}, :desc_{i}, '{s['style_parent_uuid']}'::uuid)"
            if s['style_parent_uuid'] else
            f"('{s['style_uuid']}', :name_{i}, :desc_{i}, NULL)"
            for i, s in enumerate(chunk)
        )
        params = {f"name_{i}": s['style_name'] for i, s in enumerate(chunk)}
        params.update({f"desc_{i}": s['style_description'] for i, s in enumerate(chunk)})

        query = text(f"""
            INSERT INTO style (style_uuid, style_name, style_description, style_parent_uuid)
            VALUES {values_sql}
            ON CONFLICT DO NOTHING
        """)
        await session.execute(query, params)
        await session.commit()

    # Insert mappings
    for chunk in [mappings[i:i + 1000] for i in range(0, len(mappings), 1000)]:
        values_sql = ", ".join(
            f"('{m['from_style_uuid']}', '{m['to_style_uuid']}')" for m in chunk
        )
        query = text(f"""
            INSERT INTO style_style_mapping (from_style_uuid, to_style_uuid)
            VALUES {values_sql}
            ON CONFLICT DO NOTHING
        """)
        await session.execute(query)
        await session.commit()


async def main():
    path = os.path.join(script_dir, "rym_genre.csv")
    async for session in get_async_session():
        await load_styles_from_csv(session, path)


if __name__ == "__main__":
    asyncio.run(main())
