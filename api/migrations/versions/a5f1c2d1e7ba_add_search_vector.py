from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a5f1c2d1e7ba"
down_revision = '7c974afc9105'
depends_on = None
branch_labels = None


def upgrade():
    # Create materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW search_index AS
        SELECT
            a.album_uuid AS entity_uuid,
            'album' AS entity_type,
            a.title AS display_title,
            to_tsvector(
                'english',
                coalesce(a.title, '') || ' ' ||
                coalesce(string_agg(art.name, ' '), '')
            ) AS search_vector
        FROM album a
        LEFT JOIN album_artist_bridge b ON a.album_uuid = b.album_uuid
        LEFT JOIN artist art ON b.artist_uuid = art.artist_uuid
        GROUP BY a.album_uuid, a.title

        UNION ALL

        SELECT
            artist.artist_uuid AS entity_uuid,
            'artist' AS entity_type,
            artist.name AS display_title,
            to_tsvector('english', coalesce(artist.name, '')) AS search_vector
        FROM artist;
    """)

    # Add GIN index for full-text search
    op.execute("""
        CREATE INDEX idx_search_index_vector ON search_index USING GIN (search_vector);
    """)

    # Add unique index to support CONCURRENT refreshes
    op.execute("""
        CREATE UNIQUE INDEX idx_search_index_uuid ON search_index (entity_type, entity_uuid);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_search_index_vector;")
    op.execute("DROP INDEX IF EXISTS idx_search_index_uuid;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS search_index;")
