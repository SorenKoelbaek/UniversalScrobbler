import asyncio
from typing import List
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, update
from uuid import UUID
import os
import sys
from sqlalchemy import select
# Fix Python paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dependencies.database import get_async_session
from models.sqlmodels import AlbumVector

BATCH_SIZE = 500
ORIGINAL_DIM = 5478
REDUCED_DIM = 1024



async def fetch_style_vectors(session: AsyncSession):
    result = await session.execute(
        select(AlbumVector.album_uuid, AlbumVector.style_vector).where(AlbumVector.style_vector.is_not(None))
    )
    rows = result.all()
    return [(row[0], np.array(row[1], dtype=np.float32)) for row in rows]

async def update_reduced_vectors(session: AsyncSession, updates: List[tuple[UUID, np.ndarray]]):
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        for album_uuid, reduced_vec in batch:
            await session.execute(
                update(AlbumVector)
                .where(AlbumVector.album_uuid == album_uuid)
                .values(style_vector_reduced=reduced_vec.tolist())
            )
        await session.commit()
        print(f"✅ Wrote {i + len(batch)} / {len(updates)}")


async def create_vector_indexes(session: AsyncSession):
    print("🔧 Creating indexes for vector search...")
    index_sqls = [
        "CREATE INDEX IF NOT EXISTS album_vector_style_ivfflat ON album_vector USING ivfflat (style_vector_reduced vector_cosine_ops) WITH (lists = 75);",
        "CREATE INDEX IF NOT EXISTS album_vector_artist_ivfflat ON album_vector USING ivfflat (artist_vector vector_cosine_ops) WITH (lists = 2000);",
        "CREATE INDEX IF NOT EXISTS album_vector_type_ivfflat ON album_vector USING ivfflat (type_vector vector_cosine_ops) WITH (lists = 7);",
        "CREATE INDEX IF NOT EXISTS album_vector_year_ivfflat ON album_vector USING ivfflat (year_vector vector_l2_ops) WITH (lists = 11);"
    ]
    for sql in index_sqls:
        await session.execute(text(sql))
    await session.commit()
    print("✅ Index creation complete.")


async def reduce_and_store_style_vectors():
    async for session in get_async_session():
        vectors = await fetch_style_vectors(session)

        if not vectors:
            print("❌ No style vectors found.")
            return

        uuids, matrix = zip(*vectors)
        matrix = np.stack(matrix)

        print("📉 Fitting TruncatedSVD...")
        svd = TruncatedSVD(n_components=REDUCED_DIM, n_iter=10, random_state=42)
        reduced_matrix = svd.fit_transform(matrix)

        print("🧠 Explained variance:", svd.explained_variance_ratio_.sum())

        updates = list(zip(uuids, reduced_matrix))
        await update_reduced_vectors(session, updates)

        await create_vector_indexes(session)
        print("🎉 Done: Reduced and stored all style vectors.")


if __name__ == "__main__":
    asyncio.run(reduce_and_store_style_vectors())
