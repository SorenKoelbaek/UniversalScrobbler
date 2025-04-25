from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2a5dc1e3f9a"
down_revision = "a5f1c2d1e7ba"  # Adjust to match your previous working revision
branch_labels = None
depends_on = None


def upgrade():
    # Create the materialized view for scrobble resolution
    op.execute("""
        CREATE MATERIALIZED VIEW scrobble_resolution_index AS
        SELECT
            t.track_uuid,
            t.name AS track_name,
            a.artist_uuid,
            a.name AS artist_name,
            al.album_uuid,
            al.title AS album_title,
            to_tsvector(
                'english',
                coalesce(t.name, '') || ' ' ||
                coalesce(a.name, '') || ' ' ||
                coalesce(al.title, '')
            ) AS search_vector
        FROM track t
        JOIN track_album_bridge tab ON t.track_uuid = tab.track_uuid
        JOIN album al ON tab.album_uuid = al.album_uuid
        JOIN album_artist_bridge aab ON al.album_uuid = aab.album_uuid
        JOIN artist a ON aab.artist_uuid = a.artist_uuid;
    """)

    # Add GIN index for full-text search
    op.execute("""
        CREATE INDEX idx_scrobble_search_vector ON scrobble_resolution_index USING GIN (search_vector);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_scrobble_search_vector;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_index;")