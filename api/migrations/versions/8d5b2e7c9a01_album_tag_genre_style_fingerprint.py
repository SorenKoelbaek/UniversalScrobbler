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
down_revision: Union[str, None] = '4a7c5c23d9b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create materialized view
    op.execute("""DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint CASCADE;""")
    op.execute("""DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint CASCADE;""")

    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS album_tag_genre_style_fingerprint AS
WITH mapped_tags AS (
    SELECT 
        atb.album_uuid,
        atb.tag_uuid,
        tgm.genre_name,
        tgm.style_name,
        atb.count AS tag_count
    FROM album_tag_bridge atb
    INNER JOIN tag_genre_mapping tgm
        ON atb.tag_uuid = tgm.tag_uuid
),
genre_tags AS (
    SELECT 
        album_uuid,
        tag_uuid,
        genre_name AS genre_or_style,
        'genre' AS type,
        SUM(tag_count) AS tag_count
    FROM mapped_tags
    WHERE genre_name IS NOT NULL
    GROUP BY album_uuid, tag_uuid, genre_name
),
style_tags AS (
    SELECT 
        album_uuid,
        tag_uuid,
        style_name AS genre_or_style,
        'style' AS type,
        SUM(tag_count) AS tag_count
    FROM mapped_tags
    WHERE style_name IS NOT NULL
    GROUP BY album_uuid, tag_uuid, style_name
),
combined_tags AS (
    SELECT * FROM genre_tags
    UNION ALL
    SELECT * FROM style_tags
),
genre_style_totals AS (
    SELECT 
        album_uuid,
        genre_or_style,
        type,
        SUM(tag_count) AS total_count
    FROM combined_tags
    GROUP BY album_uuid, genre_or_style, type
)
SELECT
    ct.album_uuid,
    ct.tag_uuid,
    ct.genre_or_style,
    ct.type,
    ct.tag_count,
    ct.tag_count * 1.0 / gst.total_count AS tag_weight
FROM combined_tags ct
JOIN genre_style_totals gst
  ON ct.album_uuid = gst.album_uuid
 AND ct.genre_or_style = gst.genre_or_style
 AND ct.type = gst.type;
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

# Create artist_album_tag_fingerprint only if it doesn't already exist
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS artist_album_tag_fingerprint AS
    SELECT
      aab.artist_uuid,
      atf.album_uuid,
      alb.title     AS album_title,
      alb.release_date,
      atf.tag_uuid,
      atf.tag_count,
      atf.tag_weight
    FROM album_tag_genre_style_fingerprint atf
    JOIN album alb
      ON alb.album_uuid = atf.album_uuid
    JOIN album_artist_bridge aab
      ON aab.album_uuid = alb.album_uuid;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_artist_uuid ON artist_album_tag_fingerprint (artist_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_album_uuid ON artist_album_tag_fingerprint (album_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_tag_uuid ON artist_album_tag_fingerprint (tag_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_tag_weight ON artist_album_tag_fingerprint (tag_weight);")

def downgrade() -> None:
    # Drop materialized views and related indexes
    op.execute("DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_artist_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_tag_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_tag_weight;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_genre_or_style;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_type;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_tag_weight;")
