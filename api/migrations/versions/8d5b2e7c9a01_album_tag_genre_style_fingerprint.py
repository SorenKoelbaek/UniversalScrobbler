"""Create album_tag_genre_style_fingerprint materialized view

Revision ID: 8d5b2e7c9a01
Revises: 7f3b0d2e89f2
Create Date: 2025-04-28 21:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '8d5b2e7c9a01'
down_revision: Union[str, None] = '7f3b0d2e89f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create materialized view
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS album_tag_genre_style_fingerprint AS
    WITH mapped_tags AS (
        SELECT 
            atb.album_uuid,
            tgm.genre_name,
            tgm.style_name,
            atb.count AS tag_count
        FROM album_tag_bridge atb
        INNER JOIN tag_genre_mapping tgm
          ON atb.tag_uuid = tgm.tag_uuid
    ),
    genre_counts AS (
        SELECT 
            album_uuid,
            genre_name AS genre_or_style,
            'genre' AS type,
            SUM(tag_count) AS total_count
        FROM mapped_tags
        WHERE genre_name IS NOT NULL
        GROUP BY album_uuid, genre_name
    ),
    style_counts AS (
        SELECT 
            album_uuid,
            style_name AS genre_or_style,
            'style' AS type,
            SUM(tag_count) AS total_count
        FROM mapped_tags
        WHERE style_name IS NOT NULL
        GROUP BY album_uuid, style_name
    ),
    combined_counts AS (
        SELECT * FROM genre_counts
        UNION ALL
        SELECT * FROM style_counts
    ),
    album_totals AS (
        SELECT album_uuid, SUM(total_count) AS total_count
        FROM combined_counts
        GROUP BY album_uuid
    )
    SELECT
        cc.album_uuid,
        cc.genre_or_style,
        cc.type,
        cc.total_count AS tag_count,
        cc.total_count * 1.0 / at.total_count AS tag_weight
    FROM combined_counts cc
    JOIN album_totals at ON cc.album_uuid = at.album_uuid;
    """)

    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_album_uuid 
        ON album_tag_genre_style_fingerprint (album_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_genre_or_style 
        ON album_tag_genre_style_fingerprint (genre_or_style);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_type 
        ON album_tag_genre_style_fingerprint (type);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_tag_weight 
        ON album_tag_genre_style_fingerprint (tag_weight);
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_genre_or_style;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_type;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_tag_weight;")
