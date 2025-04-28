"""Add album_feature_sparse materialized view

Revision ID: 8d5b2e7c9a02
Revises: 8d5b2e7c9a01
Create Date: 2025-04-28 22:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8d5b2e7c9a02'
down_revision: Union[str, None] = '8d5b2e7c9a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS album_feature_sparse AS
    WITH feature_list AS (
        SELECT DISTINCT genre_or_style
        FROM album_tag_genre_style_fingerprint
    ),
    feature_indexed AS (
        SELECT
            genre_or_style,
            ROW_NUMBER() OVER (ORDER BY genre_or_style) - 1 AS feature_index
        FROM feature_list
    )
    SELECT
        atgsf.album_uuid,
        fi.feature_index,
        atgsf.tag_weight
    FROM album_tag_genre_style_fingerprint atgsf
    JOIN feature_indexed fi
      ON atgsf.genre_or_style = fi.genre_or_style;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_album_feature_sparse_album_uuid ON album_feature_sparse (album_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_album_feature_sparse_feature_index ON album_feature_sparse (feature_index);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_album_feature_sparse_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_feature_sparse_feature_index;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_feature_sparse;")
