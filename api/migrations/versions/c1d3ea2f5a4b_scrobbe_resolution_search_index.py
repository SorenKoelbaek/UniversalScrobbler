from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c1d3ea2f5a4b"  # NEW REVISION (adjust as needed)
down_revision = "b2a5dc1e3f9a"  # Points to your last migration
branch_labels = None
depends_on = None


def upgrade():
    # Create the new materialized view for refined scrobble resolution
    op.execute("""
        CREATE MATERIALIZED VIEW scrobble_resolution_search_index AS
        SELECT
            t.track_uuid,
            t.name AS track_name,
            a.artist_uuid,
            a.name AS artist_name,
            al.album_uuid,
            al.title AS album_title,
            to_tsvector('simple', coalesce(t.name, '')) AS track_name_vector,
            to_tsvector('simple', coalesce(a.name, '')) AS artist_name_vector,
            to_tsvector('simple', coalesce(al.title, '')) AS album_title_vector
        FROM track t
        JOIN track_album_bridge tab ON t.track_uuid = tab.track_uuid
        JOIN album al ON tab.album_uuid = al.album_uuid
        JOIN album_artist_bridge aab ON al.album_uuid = aab.album_uuid
        JOIN artist a ON aab.artist_uuid = a.artist_uuid;
    """)

    # Create GIN indexes on each tsvector column
    op.execute("""
        CREATE INDEX idx_scrobble_track_name_vector ON scrobble_resolution_search_index USING GIN (track_name_vector);
    """)
    op.execute("""
        CREATE INDEX idx_scrobble_artist_name_vector ON scrobble_resolution_search_index USING GIN (artist_name_vector);
    """)
    op.execute("""
        CREATE INDEX idx_scrobble_album_title_vector ON scrobble_resolution_search_index USING GIN (album_title_vector);
    """)


def downgrade():
    # Drop indexes and materialized view in reverse order
    op.execute("DROP INDEX IF EXISTS idx_scrobble_album_title_vector;")
    op.execute("DROP INDEX IF EXISTS idx_scrobble_artist_name_vector;")
    op.execute("DROP INDEX IF EXISTS idx_scrobble_track_name_vector;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_search_index;")
