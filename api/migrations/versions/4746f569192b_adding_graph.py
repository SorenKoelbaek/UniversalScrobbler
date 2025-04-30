"""adding graph

Revision ID: 4746f569192b
Revises: c3b7d5f914a2
Create Date: 2025-04-30 23:36:21.439078
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# ✅ Import Vector type from pgvector
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '4746f569192b'
down_revision: Union[str, None] = 'c3b7d5f914a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ✅ Ensure the pgvector extension is installed

    # ✅ Create album_graph_embedding table with real pgvector column
    op.create_table(
        'album_graph_embedding',
        sa.Column('album_uuid', sa.Uuid(), nullable=False),
        sa.Column('embedding', Vector(128), nullable=False),
        sa.PrimaryKeyConstraint('album_uuid')
    )

    # Optional: drop a no-longer-used table
    op.drop_table('flexible_tag_mapping')


def downgrade() -> None:
    op.create_table(
        'flexible_tag_mapping',
        sa.Column('from_tag_uuid', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('to_tag_uuid', sa.UUID(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['from_tag_uuid'], ['tag.tag_uuid'], name='flexible_tag_mapping_from_tag_uuid_fkey'),
        sa.ForeignKeyConstraint(['to_tag_uuid'], ['tag.tag_uuid'], name='flexible_tag_mapping_to_tag_uuid_fkey'),
        sa.PrimaryKeyConstraint('from_tag_uuid', 'to_tag_uuid', name='flexible_tag_mapping_pkey')
    )
    op.drop_table('album_graph_embedding')
