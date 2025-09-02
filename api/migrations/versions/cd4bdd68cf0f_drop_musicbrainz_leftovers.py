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
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_search_index")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS scrobble_resolution_index")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS artist_album_tag_fingerprint")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS album_tag_genre_style_fingerprint")

    # 2. Drop index
    op.execute("DROP INDEX IF EXISTS ix_album_vector_album_uuid")

    # 3. Drop tables
    op.execute("DROP TABLE IF EXISTS album_vector")
    op.execute("DROP TABLE IF EXISTS tag_genre_mapping")
    op.execute("DROP TABLE IF EXISTS tag_style_match")
    op.execute("DROP TABLE IF EXISTS style_style_mapping")
    op.execute("DROP TABLE IF EXISTS style")
    op.execute("DROP TABLE IF EXISTS spotifytoken")
    op.execute("DROP TABLE IF EXISTS discogs_track")

    # 4. Recreate FK correctly
    op.execute(
        "ALTER TABLE playback_history DROP CONSTRAINT IF EXISTS playback_history_track_uuid_fkey"
    )
    op.execute(
        "ALTER TABLE playback_history "
        "ADD CONSTRAINT playback_history_track_uuid_fkey "
        "FOREIGN KEY (track_uuid) REFERENCES track(track_uuid)"
    )


def downgrade() -> None:
    pass
