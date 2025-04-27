"""
Create album_tag_fingerprint and artist_album_tag_fingerprint materialized views (3‑step pre‑aggregation)

Revision ID: 7f3b0d2e89f2
Revises: 4a7c5c23d9b8
Create Date: 2025-04-27 17:10:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '7f3b0d2e89f2'
down_revision: Union[str, None] = '4a7c5c23d9b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create album_tag_fingerprint only if it doesn't already exist
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS album_tag_fingerprint AS
    WITH atb AS (
      SELECT album_uuid, tag_uuid, COUNT(*) AS ct
      FROM album_tag_bridge
      GROUP BY album_uuid, tag_uuid
    ),
    art AS (
      SELECT ar.album_uuid, artb.tag_uuid, COUNT(*) AS ct
      FROM album_release ar
      JOIN album_release_tag_bridge artb
        ON ar.album_release_uuid = artb.album_release_uuid
      GROUP BY ar.album_uuid, artb.tag_uuid
    ),
    tab AS (
      SELECT tab.album_uuid, tvtb.tag_uuid, COUNT(*) AS ct
      FROM track_album_bridge tab
      JOIN track_version tv
        ON tab.track_uuid = tv.track_uuid
      JOIN track_version_tag_bridge tvtb
        ON tv.track_version_uuid = tvtb.track_version_uuid
      GROUP BY tab.album_uuid, tvtb.tag_uuid
    ),
    tag_counts AS (
      SELECT album_uuid, tag_uuid, SUM(ct) AS tag_count
      FROM (
        SELECT * FROM atb
        UNION ALL
        SELECT * FROM art
        UNION ALL
        SELECT * FROM tab
      ) u
      GROUP BY album_uuid, tag_uuid
    ),
    album_totals AS (
      SELECT album_uuid, SUM(tag_count) AS total_count
      FROM tag_counts
      GROUP BY album_uuid
    )
    SELECT
      tc.album_uuid,
      tc.tag_uuid,
      tc.tag_count,
      tc.tag_count * 1.0 / at.total_count AS tag_weight
    FROM tag_counts tc
    JOIN album_totals at USING (album_uuid);
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_album_tag_fingerprint_album_uuid ON album_tag_fingerprint (album_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_album_tag_fingerprint_tag_uuid ON album_tag_fingerprint (tag_uuid);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_album_tag_fingerprint_tag_weight ON album_tag_fingerprint (tag_weight);")

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
    FROM album_tag_fingerprint atf
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
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_fingerprint;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_fingerprint_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_fingerprint_tag_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_fingerprint_tag_weight;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_artist_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_tag_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_tag_weight;")
