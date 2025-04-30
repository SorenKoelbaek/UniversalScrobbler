import os
import sys
import asyncio
import re
import csv
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, Field
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sklearn.metrics.pairwise import cosine_similarity
from nltk.stem import WordNetLemmatizer
import nltk
from sentence_transformers import SentenceTransformer

# --- Fix Python paths ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Setup nltk wordnet path ---
nltk.data.path.append(os.path.join(script_dir, "wordnet"))
lemmatizer = WordNetLemmatizer()

# --- Load project-specific modules ---
from dependencies.database import get_async_session
from models.sqlmodels import TagStyleMatch

# --- Normalization map support ---
def load_normalization_map(csv_path: str) -> dict:
    variant_map = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                variant = row["variant"].lower()
                normalized_target = row["normalized"]
                variant_map[variant] = normalized_target
    except FileNotFoundError:
        print(f"⚠️ Normalization CSV not found at {csv_path}, continuing without it.")
    return variant_map

normalization_map = load_normalization_map(os.path.join(script_dir, "normalization.csv"))

def enrich_for_embedding(text: str) -> str:
    return f"{text} music genre"

async def get_eligible_tags(session: AsyncSession):
    result = await session.execute(
        text("""
            WITH tag_aggregates AS (
                SELECT tag_uuid, COUNT(*) AS uses, 'album' AS bridge_type FROM album_tag_bridge GROUP BY tag_uuid
                UNION ALL
                SELECT tag_uuid, COUNT(*) AS uses, 'album_release' FROM album_release_tag_bridge GROUP BY tag_uuid
                UNION ALL
                SELECT tag_uuid, COUNT(*) AS uses, 'artist' FROM artist_tag_bridge GROUP BY tag_uuid
                UNION ALL
                SELECT tag_uuid, COUNT(*) AS uses, 'track_version' FROM track_version_tag_bridge GROUP BY tag_uuid
            ),
            tag_usage_summary AS (
                SELECT
                    tag_uuid,
                    SUM(uses) AS total_uses,
                    COUNT(DISTINCT bridge_type) AS bridge_type_count
                FROM
                    tag_aggregates
                GROUP BY
                    tag_uuid
            )
            SELECT
                t.tag_uuid,
                t.name
            FROM
                tag_usage_summary u
            JOIN
                tag t ON t.tag_uuid = u.tag_uuid
            WHERE
                u.total_uses > 3
                AND u.bridge_type_count > 1
        """)
    )
    return result.all()

def split_tag_name(tag_name: str):
    return [p.strip() for p in re.split(r"[;,/:]", tag_name) if p.strip()]

async def map_tags_to_styles(session: AsyncSession):
    matching_criteria = 0.60
    fallback_criteria = 0.70
    closeness_criteria = 0.02

    print("✅ Loading tags and styles from database...")

    tags = await get_eligible_tags(session)

    result = await session.execute(
        text("SELECT style_uuid, style_name, style_description FROM style")
    )
    styles = result.all()

    tag_rows = [(tag_uuid, name.strip()) for tag_uuid, name in tags]
    style_names = [row[1].strip() for row in styles]
    style_uuids = [row[0] for row in styles]
    style_descriptions = [(row[2] or "").strip() for row in styles]

    # Build clean style name lookup
    style_name_lower_to_uuid = {name.lower(): uuid for name, uuid in zip(style_names, style_uuids)}
    raw_styles = dict(zip(style_names, style_uuids))

    print(f"✅ Loaded {len(tag_rows)} tags and {len(style_names)} styles.")

    model = SentenceTransformer('all-mpnet-base-v2')

    # --- Normalize and enrich styles before embedding ---
    style_texts = [
        f"{name}. {name}. {description}" if description else f"{name}. {name}"
        for name, description in zip(style_names, style_descriptions)
    ]
    style_embeddings = model.encode(style_texts, normalize_embeddings=True)

    batch_parts = []
    batch_metadata = []
    matches_to_insert = []

    print("✅ Phase 1: Manual override mapping...")

    for tag_uuid, tag_name in tag_rows:
        raw_tag_clean = tag_name.strip()

        # 1. Manual override via normalization.csv
        normalization_target = normalization_map.get(raw_tag_clean)
        if normalization_target:
            # 2. Try match normalized_target to style_name exactly (lower for safety)
            for style_name, style_uuid in raw_styles.items():
                if normalization_target.lower() == style_name.lower():
                    matches_to_insert.append(TagStyleMatch(
                        tag_uuid=str(tag_uuid),
                        style_uuid=style_uuid
                    ))
                    break
            else:
                # No manual match found -> fallback
                split_parts = split_tag_name(tag_name)
                for part in split_parts:
                    enriched_part = enrich_for_embedding(part.lower())
                    batch_parts.append(enriched_part)
                    batch_metadata.append({
                        "tag_uuid": str(tag_uuid),
                        "tag_name": part,
                    })
            continue  # Done with this tag (either matched or prepared fallback)

        # No normalization, fallback
        split_parts = split_tag_name(tag_name)
        for part in split_parts:
            enriched_part = enrich_for_embedding(part.lower())
            batch_parts.append(enriched_part)
            batch_metadata.append({
                "tag_uuid": str(tag_uuid),
                "tag_name": part,
            })

    print(f"✅ {len(matches_to_insert)} direct manual matches found.")
    print(f"✅ {len(batch_parts)} parts prepared for fallback matching.")

    # Phase 2: Embedding fallback
    if batch_parts:
        batch_embeddings = model.encode(batch_parts, normalize_embeddings=True)

        similarities = cosine_similarity(batch_embeddings, style_embeddings)

        for i, scores in enumerate(similarities):
            best_idx = scores.argmax()
            best_score = scores[best_idx]

            high_score_indices = np.where((scores >= matching_criteria) & (scores >= best_score - closeness_criteria))[0]

            if len(high_score_indices) > 0:
                matched_style = style_names[best_idx]
                style_uuid = raw_styles.get(matched_style)
                if style_uuid:
                    matches_to_insert.append(TagStyleMatch(
                        tag_uuid=batch_metadata[i]["tag_uuid"],
                        style_uuid=style_uuid
                    ))

    # Insert matches into database (conflict-safe)
    if matches_to_insert:
        values = [{"tag_uuid": m.tag_uuid, "style_uuid": m.style_uuid} for m in matches_to_insert]

        stmt = pg_insert(TagStyleMatch).values(values)
        stmt = stmt.on_conflict_do_nothing(index_elements=["tag_uuid", "style_uuid"])

        await session.execute(stmt)
        await session.commit()

        print(f"✅ Inserted {len(matches_to_insert)} tag-style matches into the database (conflicts ignored).")
    else:
        print(f"⚠️ No tag-style matches found.")

async def main():
    async for session in get_async_session():
        await map_tags_to_styles(session)

if __name__ == "__main__":
    asyncio.run(main())
