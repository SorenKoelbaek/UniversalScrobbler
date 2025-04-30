import os
import sys
import asyncio
from uuid import UUID
from collections import defaultdict

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.data import Data
from torch_geometric.loader import NeighborLoader
from torch_geometric.nn import SAGEConv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fix Python paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Project imports
from dependencies.database import get_async_session
from models.sqlmodels import AlbumGraphEmbedding

# ─────── GraphSAGE Model ───────
class GraphSAGE(nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.conv2(x, edge_index)
        return x

# ─────── Load Data ───────
async def load_graph_data(session: AsyncSession):
    print("📥 Loading style fingerprints...")
    result = await session.execute(text("""
        SELECT album_uuid, style_uuid, tag_weight FROM album_tag_genre_style_fingerprint
    """))
    style_rows = result.fetchall()

    release_result = await session.execute(text("""
        SELECT album_uuid, release_date FROM album
        WHERE album_uuid IN (SELECT DISTINCT album_uuid FROM album_tag_genre_style_fingerprint)
    """))
    release_dates = dict(release_result.fetchall())

    artist_result = await session.execute(text("""
        SELECT artist_uuid, album_uuid FROM album_artist_bridge
        WHERE album_uuid IN (SELECT DISTINCT album_uuid FROM album_tag_genre_style_fingerprint)
    """))
    artist_links = artist_result.fetchall()

    style_edges = await session.execute(text("""
        SELECT from_style_uuid, to_style_uuid FROM style_style_mapping
    """))
    style_edges = style_edges.fetchall()

    style_set = {style_uuid for _, style_uuid, _ in style_rows}
    style_list = sorted(style_set)
    style_to_idx = {str(s): i for i, s in enumerate(style_list)}
    num_styles = len(style_list)

    # Album feature vectors
    album_features = defaultdict(lambda: torch.zeros(num_styles + 1))  # +1 for year
    for album_uuid, style_uuid, tag_weight in style_rows:
        idx = style_to_idx[str(style_uuid)]
        album_features[album_uuid][idx] = float(tag_weight)

    for album_uuid, date_obj in release_dates.items():
        year = date_obj.year if date_obj else 1900
        album_features[album_uuid][-1] = year / 2550.0  # normalized

    album_uuids = set(album_features.keys())
    artist_uuids = {a for a, _ in artist_links}
    style_uuids = style_set | {s for pair in style_edges for s in pair}
    all_uuids = list(artist_uuids | album_uuids | style_uuids)
    uuid_to_idx = {str(u): i for i, u in enumerate(all_uuids)}
    idx_to_album = {uuid_to_idx[str(a)]: a for a in album_uuids}

    num_nodes = len(all_uuids)
    x = torch.zeros((num_nodes, num_styles + 1))

    for album_uuid, vec in album_features.items():
        idx = uuid_to_idx[str(album_uuid)]
        x[idx] = vec

    edge_index = []
    for artist_uuid, album_uuid in artist_links:
        edge_index.append([uuid_to_idx[str(artist_uuid)], uuid_to_idx[str(album_uuid)]])
    for album_uuid, style_uuid, _ in style_rows:
        edge_index.append([uuid_to_idx[str(album_uuid)], uuid_to_idx[str(style_uuid)]])
    for from_uuid, to_uuid in style_edges:
        edge_index.append([uuid_to_idx[str(from_uuid)], uuid_to_idx[str(to_uuid)]])

    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    return Data(x=x, edge_index=edge_index), idx_to_album

# ─────── Train and Store ───────
async def train_and_store(session: AsyncSession):
    data, idx_to_album = await load_graph_data(session)

    loader = NeighborLoader(
        data,
        input_nodes=None,
        num_neighbors=[25, 10],
        batch_size=2048,
        shuffle=True
    )

    model = GraphSAGE(data.num_node_features, 64, 128)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)

    print("🧠 Training GraphSAGE...")
    model.train()
    for epoch in range(10):
        total_loss = 0
        for batch in loader:
            optimizer.zero_grad()
            out = model(batch.x, batch.edge_index)
            loss = out.norm(p=2).mean()  # ✅ no mismatch
            loss.backward()
            optimizer.step()
        print(f"Epoch {epoch:02d} | Loss: {total_loss:.4f}")

    print("💾 Saving album embeddings...")
    model.eval()
    with torch.no_grad():
        all_embeddings = model(data.x, data.edge_index)

    await session.execute(text("TRUNCATE TABLE album_graph_embedding;"))
    for idx, album_uuid in idx_to_album.items():
        emb = all_embeddings[idx].tolist()
        session.add(AlbumGraphEmbedding(album_uuid=album_uuid, embedding=emb))
    await session.commit()
    print(f"✅ Stored {len(idx_to_album)} album embeddings.")

# ─────── Entrypoint ───────
async def main():
    async for session in get_async_session():
        await train_and_store(session)

if __name__ == "__main__":
    asyncio.run(main())
