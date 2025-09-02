"""drop musicbrainz leftovers

Revision ID: cd4bdd68cf0f
Revises: f166b077285e
Create Date: 2025-09-02 00:41:53.483709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cd4bdd68cf0f'
down_revision: Union[str, None] = 'f166b077285e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop materialized views that were left behind
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_index CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_search_index CASCADE")

    op.drop_index('ix_album_vector_album_uuid', table_name='album_vector')
    op.drop_table('album_vector')
    op.drop_table('tag_genre_mapping')
    op.drop_table('tag_style_match')

    op.drop_table('style_style_mapping')
    op.drop_table('style')
    op.drop_table('spotifytoken')

    op.drop_constraint('playback_history_track_uuid_fkey', 'playback_history', type_='foreignkey')
    op.create_foreign_key(
        "playback_history_track_uuid_fkey",
        "playback_history",
        "track",
        ["track_uuid"],
        ["track_uuid"],
    )
    op.drop_table('discogs_track')
    # ### end Alembic commands ###


def downgrade() -> None:
    pass
