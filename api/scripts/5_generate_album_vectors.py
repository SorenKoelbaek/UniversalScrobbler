import os
import sys
import asyncio
from uuid import UUID
from typing import Dict, List, Tuple, DefaultDict
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import numpy as np
import mmh3

from sklearn.decomposition import IncrementalPCA
from sklearn.preprocessing import normalize

# Fix Python paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dependencies.database import get_async_session
from models.sqlmodels import AlbumVector

MAX_STYLE_DIM = 5478
ARTIST_VECTOR_DIM = 512
YEAR_VECTOR_DIM = 1
REDUCED_DIM = 1024  # or whatever dimension you want to reduce to
BATCH_SIZE = 10000

# --- Vector helpers ---
def make_artist_vector(artist_uuids: List[UUID], dim: int = ARTIST_VECTOR_DIM) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    weight = 1.0 / np.sqrt(len(artist_uuids)) if artist_uuids else 0.0
    for artist_uuid in artist_uuids:
        idx = mmh3.hash(str(artist_uuid), signed=False) % dim
        vec[idx] += weight
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec

def normalize_year_vector(year: int) -> np.ndarray:
    return np.array([(year - 1900) / 150.0], dtype=np.float32)

def make_type_vector(type_uuids: List[UUID], type_index: Dict[UUID, int]) -> np.ndarray:
    dim = len(type_index)
    vec = np.zeros(dim, dtype=np.float32)
    for uuid in type_uuids:
        if uuid in type_index:
            vec[type_index[uuid]] = 1.0
    if np.count_nonzero(vec) == 1:
        vec *= 1.5
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec

# --- Caching helpers ---
async def load_album_type_index(session: AsyncSession) -> Dict[UUID, int]:
    result = await session.execute(text("SELECT album_type_uuid FROM album_type ORDER BY name"))
    return {row[0]: i for i, row in enumerate(result.fetchall())}

async def load_artist_and_type_maps(session: AsyncSession) -> Tuple[Dict[UUID, List[UUID]], Dict[UUID, List[UUID]]]:
    artist_map: Dict[UUID, List[UUID]] = {}
    res = await session.execute(text("SELECT album_uuid, artist_uuid FROM album_artist_bridge"))
    for album_uuid, artist_uuid in res.fetchall():
        artist_map.setdefault(album_uuid, []).append(artist_uuid)

    type_map: Dict[UUID, List[UUID]] = {}
    res = await session.execute(text("SELECT album_uuid, album_type_uuid FROM albumtypebridge"))
    for album_uuid, type_uuid in res.fetchall():
        type_map.setdefault(album_uuid, []).append(type_uuid)

    return artist_map, type_map

async def load_style_index(session: AsyncSession) -> Dict[UUID, int]:
    res = await session.execute(text("SELECT style_uuid FROM style ORDER BY style_name"))
    return {uuid: i for i, (uuid,) in enumerate(res.fetchall())}

async def load_style_parent_map(session: AsyncSession) -> Dict[UUID, List[UUID]]:
    result = await session.execute(text("SELECT to_style_uuid, from_style_uuid FROM style_style_mapping"))
    parent_map: Dict[UUID, List[UUID]] = defaultdict(list)
    for to_uuid, from_uuid in result.fetchall():
        parent_map[to_uuid].append(from_uuid)
    return parent_map

async def load_style_vectors(
    session: AsyncSession,
    style_index: Dict[UUID, int],
    parent_map: Dict[UUID, List[UUID]]
) -> Dict[UUID, np.ndarray]:
    print("📥 Preloading all style scores and parent style hierarchy...")

    result = await session.execute(text("""
        SELECT album_uuid, style_uuid, final_score
        FROM album_style_scores
    """))

    raw_scores: DefaultDict[UUID, List[Tuple[int, float]]] = defaultdict(list)

    for album_uuid, style_uuid, score in result.fetchall():
        idx = style_index.get(style_uuid)
        if idx is not None:
            raw_scores[album_uuid].append((idx, float(score)))

        for parent_uuid in parent_map.get(style_uuid, []):
            parent_idx = style_index.get(parent_uuid)
            if parent_idx is not None:
                raw_scores[album_uuid].append((parent_idx, float(score) * 0.5))

    print("🎨 Converting style scores to sparse vectors...")
    album_style_vectors: Dict[UUID, np.ndarray] = {}

    for album_uuid, items in raw_scores.items():
        aggregated = defaultdict(float)
        for idx, score in items:
            aggregated[idx] += score

        sorted_items = sorted(aggregated.items(), key=lambda x: -x[1])[:10]
        vec = np.zeros(len(style_index), dtype=np.float32)
        for idx, score in sorted_items:
            vec[idx] = score

        norm = np.linalg.norm(vec)
        album_style_vectors[album_uuid] = vec / norm if norm > 0 else vec

    return album_style_vectors

# --- Main vector generation logic ---
async def compute_and_store_album_vectors(session: AsyncSession):
    print("📥 Loading type index and artist/type maps...")
    type_index = await load_album_type_index(session)
    artist_map, type_map = await load_artist_and_type_maps(session)
    style_index = await load_style_index(session)
    style_parent_map = await load_style_parent_map(session)

    result = await session.stream(text("SELECT album_uuid, release_date FROM album"))
    albums = [row async for row in result]

    await session.execute(text("""
        CREATE TEMP VIEW album_styles_base AS
        SELECT
            album_uuid,
            style_uuid,
            SUM(tag_count)::float AS raw_style_score
        FROM album_tag_genre_style_fingerprint
        GROUP BY album_uuid, style_uuid
    """))

    await session.execute(text("""
        CREATE TEMP VIEW artist_styles_top AS
        SELECT artist_uuid, style_uuid, SUM(raw_style_score) AS total_score
        FROM (
            SELECT
                aab.artist_uuid,
                asb.style_uuid,
                asb.raw_style_score
            FROM album_styles_base asb
            JOIN album_artist_bridge aab ON asb.album_uuid = aab.album_uuid
        ) combined
        GROUP BY artist_uuid, style_uuid
    """))

    await session.execute(text("""
        CREATE TEMP TABLE album_style_scores AS
        SELECT
            asb.album_uuid,
            asb.style_uuid,
            asb.raw_style_score + COALESCE(ast.total_score * 0.2, 0) AS final_score
        FROM album_styles_base asb
        LEFT JOIN album_artist_bridge aab ON asb.album_uuid = aab.album_uuid
        LEFT JOIN artist_styles_top ast
          ON ast.artist_uuid = aab.artist_uuid AND ast.style_uuid = asb.style_uuid
    """))

    style_vectors = await load_style_vectors(session, style_index, style_parent_map)


    REDUCED_DIM = 1024
    BATCH_SIZE = 10000

    print("📉 Reducing style vectors in memory...")

    # Prepare UUID list and batching
    uuids = list(style_vectors.keys())
    ipca = IncrementalPCA(n_components=REDUCED_DIM)

    # First pass: partial fit
    print("🔁 First pass (partial_fit)...")
    for i in range(0, len(uuids), BATCH_SIZE):
        batch_vectors = [style_vectors[uuid] for uuid in uuids[i:i + BATCH_SIZE]]
        matrix = normalize(np.stack(batch_vectors), axis=1)
        ipca.partial_fit(matrix)

    # Second pass: transform and store
    print("🔁 Second pass (transform and collect)...")
    reduced_vectors = {}
    for i in range(0, len(uuids), BATCH_SIZE):
        batch_ids = uuids[i:i + BATCH_SIZE]
        batch_vectors = [style_vectors[uuid] for uuid in batch_ids]
        matrix = normalize(np.stack(batch_vectors), axis=1)
        reduced_batch = ipca.transform(matrix)
        reduced_vectors.update(zip(batch_ids, reduced_batch))

    print(f"🎯 Processing {len(albums)} albums...")
    await session.execute(text("TRUNCATE TABLE album_vector;"))

    for i, (album_uuid, release_date) in enumerate(albums):
        year = release_date.year if release_date else 1900
        year_vector = normalize_year_vector(year)

        artist_uuids = artist_map.get(album_uuid, [])
        artist_vector = make_artist_vector(artist_uuids)

        type_uuids = type_map.get(album_uuid, [])
        type_vector = make_type_vector(type_uuids, type_index)

        style_vector = reduced_vectors.get(album_uuid, np.zeros(REDUCED_DIM, dtype=np.float32))

        session.add(AlbumVector(
            album_uuid=album_uuid,
            year_vector=year_vector,
            artist_vector=artist_vector,
            type_vector=type_vector,
            style_vector_reduced=style_vector
        ))

        if (i + 1) % 1000 == 0:
            await session.commit()
            print(f"✅ Committed {i + 1:,} albums...")

    await session.commit()
    print("🏁 Done! All album vectors stored.")

# --- Entrypoint ---
async def main():
    async for session in get_async_session():
        await compute_and_store_album_vectors(session)

if __name__ == "__main__":
    asyncio.run(main())
