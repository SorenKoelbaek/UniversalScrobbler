from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'c3b7d5f914a2'
down_revision: Union[str, None] = 'ef154ddf5aeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Drop old materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint;")

    # Create new materialized view (with corrected weighting logic)
    op.execute("""
    CREATE MATERIALIZED VIEW if not exists album_tag_genre_style_fingerprint AS
    WITH direct_styles AS (
        SELECT
            atb.album_uuid,
            tsm.style_uuid,
            atb.count AS tag_count
        FROM album_tag_bridge atb
        INNER JOIN tag_style_match tsm
            ON atb.tag_uuid = tsm.tag_uuid
    ),
    parent_styles AS (
        SELECT
            ds.album_uuid,
            ssm.from_style_uuid AS style_uuid,
            ds.tag_count
        FROM direct_styles ds
        INNER JOIN style_style_mapping ssm
            ON ds.style_uuid = ssm.to_style_uuid
    ),
    all_styles AS (
        SELECT * FROM direct_styles
        UNION ALL
        SELECT * FROM parent_styles
    ),
    album_style_weights AS (
        SELECT
            as1.album_uuid,
            as1.style_uuid,
            SUM(as1.tag_count) AS tag_count
        FROM all_styles as1
        GROUP BY as1.album_uuid, as1.style_uuid
    ),
    style_totals AS (
        SELECT
            album_uuid,
            SUM(tag_count) AS total_count
        FROM album_style_weights
        GROUP BY album_uuid
    )
    SELECT
        aw.album_uuid,
        aw.style_uuid,
        aw.tag_count,
        st.total_count,
        (aw.tag_count * 1.0 / st.total_count) AS tag_weight
    FROM album_style_weights aw
    JOIN style_totals st
      ON aw.album_uuid = st.album_uuid;

    """)

    # Create indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_album_uuid
        ON album_tag_genre_style_fingerprint (album_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_style_uuid
        ON album_tag_genre_style_fingerprint (style_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_album_tag_genre_style_tag_weight
        ON album_tag_genre_style_fingerprint (tag_weight);
    """)

    # Create artist-album view
    op.execute("""
    CREATE MATERIALIZED VIEW IF NOT EXISTS artist_album_tag_fingerprint AS
    WITH artist_album_data AS (
        SELECT
            album_artist_bridge.artist_uuid,
            album_tag_genre_style_fingerprint.album_uuid,
            album.release_date,
            album.title AS album_title,
            album_tag_genre_style_fingerprint.style_uuid,
            album_tag_genre_style_fingerprint.tag_count,
            album_tag_genre_style_fingerprint.tag_weight
        FROM album_tag_genre_style_fingerprint
        JOIN album
          ON album_tag_genre_style_fingerprint.album_uuid = album.album_uuid
        JOIN album_artist_bridge
          ON album_artist_bridge.album_uuid = album.album_uuid
    ),
    artist_totals AS (
        SELECT
            artist_album_data.artist_uuid,
            SUM(artist_album_data.tag_count) AS total_tag_count,
            COUNT(DISTINCT artist_album_data.style_uuid) AS unique_styles
        FROM artist_album_data
        GROUP BY artist_album_data.artist_uuid
    ),
    album_style_count AS (
        SELECT
            artist_album_data.artist_uuid,
            artist_album_data.album_uuid,
            COUNT(DISTINCT artist_album_data.style_uuid) AS styles_on_album
        FROM artist_album_data
        GROUP BY artist_album_data.artist_uuid, artist_album_data.album_uuid
    )
    SELECT
        artist_album_data.artist_uuid,
        artist_album_data.album_uuid,
        artist_album_data.album_title,
        artist_album_data.release_date,
        artist_album_data.style_uuid,
        artist_album_data.tag_count,
        artist_album_data.tag_weight,
        (artist_album_data.tag_count * 1.0 / artist_totals.total_tag_count) AS album_weight,
        (album_style_count.styles_on_album * 1.0 / artist_totals.unique_styles) AS artist_weight
    FROM artist_album_data
    JOIN artist_totals
      ON artist_album_data.artist_uuid = artist_totals.artist_uuid
    JOIN album_style_count
      ON artist_album_data.artist_uuid = album_style_count.artist_uuid
     AND artist_album_data.album_uuid = album_style_count.album_uuid;

    """)

    # Indexes for artist_album_tag_fingerprint
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_artist_uuid
        ON artist_album_tag_fingerprint (artist_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_album_uuid
        ON artist_album_tag_fingerprint (album_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_style_name
        ON artist_album_tag_fingerprint (style_uuid);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_artist_album_tag_fingerprint_tag_weight
        ON artist_album_tag_fingerprint (tag_weight);
    """)

def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_style_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_album_tag_genre_style_tag_weight;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_artist_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_album_uuid;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_style_name;")
    op.execute("DROP INDEX IF EXISTS idx_artist_album_tag_fingerprint_tag_weight;")
