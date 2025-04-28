import os
import sys
import asyncio
import numpy as np
import scipy.sparse
import umap
from tqdm import tqdm
from sqlalchemy import delete
from sqlmodel import select


script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dependencies.database import get_async_session
from models.sqlmodels import AlbumFeatureSparse, AlbumUMAPEmbedding

# UMAP Parameters
N_NEIGHBORS = 30
MIN_DIST = 0.1
N_COMPONENTS = 2
METRIC = "cosine"


async def fetch_album_features(session):
    result = await session.execute(
        select(AlbumFeatureSparse.album_uuid, AlbumFeatureSparse.feature_index, AlbumFeatureSparse.tag_weight)
    )
    rows = result.all()

    album_uuid_list = []
    album_uuid_to_index = {}

    for album_uuid in {row[0] for row in rows}:
        idx = len(album_uuid_list)
        album_uuid_list.append(album_uuid)
        album_uuid_to_index[album_uuid] = idx

    n_albums = len(album_uuid_list)
    n_features = max(row[1] for row in rows) + 1

    row_indices = []
    col_indices = []
    data = []

    for album_uuid, feature_index, tag_weight in rows:
        row_indices.append(album_uuid_to_index[album_uuid])
        col_indices.append(feature_index)
        data.append(tag_weight)

    sparse_matrix = scipy.sparse.csr_matrix((data, (row_indices, col_indices)), shape=(n_albums, n_features))

    return sparse_matrix, album_uuid_list


def run_umap(sparse_matrix):
    reducer = umap.UMAP(
        n_neighbors=N_NEIGHBORS,
        min_dist=MIN_DIST,
        n_components=N_COMPONENTS,
        metric=METRIC,
        random_state=42,
        verbose=True,
    )
    return reducer.fit_transform(sparse_matrix)


async def save_embeddings(session, album_uuid_list, embedding):
    print("Saving UMAP embeddings into album_umap_embedding...")

    # Clear existing embeddings
    await session.execute(delete(AlbumUMAPEmbedding))

    # Bulk insert
    objects = [
        AlbumUMAPEmbedding(album_uuid=album_uuid, x=float(vec[0]), y=float(vec[1]))
        for album_uuid, vec in zip(album_uuid_list, embedding)
    ]

    session.add_all(objects)
    await session.commit()

    print(f"✅ Inserted {len(objects)} embeddings.")


async def main():
    async for session in get_async_session():
        sparse_matrix, album_uuid_list = await fetch_album_features(session)
        embedding = run_umap(sparse_matrix)
        await save_embeddings(session, album_uuid_list, embedding)


if __name__ == "__main__":
    asyncio.run(main())
