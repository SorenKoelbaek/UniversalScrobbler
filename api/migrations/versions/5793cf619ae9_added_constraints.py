"""added constraints

Revision ID: 5793cf619ae9
Revises: 0fe4eea4193e
Create Date: 2025-09-19 16:25:55.667356

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5793cf619ae9'
down_revision: Union[str, None] = '0fe4eea4193e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Pick canonical artist per MBID by earliest created_at
    for table in [
        "album_artist_bridge",
        "album_release_artist_bridge",
        "track_artist_bridge",
        "track_version_extra_artist",
        "artist_tag_bridge",
    ]:
        conn.execute(sa.text(f"""
            WITH ranked AS (
                SELECT artist_uuid,
                       musicbrainz_artist_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY musicbrainz_artist_id
                           ORDER BY created_at ASC
                       ) AS rn
                FROM artist
                WHERE musicbrainz_artist_id IS NOT NULL
            ),
            canon AS (
                SELECT musicbrainz_artist_id, artist_uuid AS canonical_uuid
                FROM ranked
                WHERE rn = 1
            ),
            dups AS (
                SELECT r.artist_uuid, c.canonical_uuid
                FROM ranked r
                JOIN canon c USING (musicbrainz_artist_id)
                WHERE r.rn > 1
            )
            UPDATE {table} b
            SET artist_uuid = d.canonical_uuid
            FROM dups d
            WHERE b.artist_uuid = d.artist_uuid;
        """))

    # special case: similar_artist_bridge has two artist FKs
    for col in ["artist_uuid", "reference_artist_uuid"]:
        conn.execute(sa.text(f"""
            WITH ranked AS (
                SELECT artist_uuid,
                       musicbrainz_artist_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY musicbrainz_artist_id
                           ORDER BY created_at ASC
                       ) AS rn
                FROM artist
                WHERE musicbrainz_artist_id IS NOT NULL
            ),
            canon AS (
                SELECT musicbrainz_artist_id, artist_uuid AS canonical_uuid
                FROM ranked
                WHERE rn = 1
            ),
            dups AS (
                SELECT r.artist_uuid, c.canonical_uuid
                FROM ranked r
                JOIN canon c USING (musicbrainz_artist_id)
                WHERE r.rn > 1
            )
            UPDATE similar_artist_bridge sab
            SET {col} = d.canonical_uuid
            FROM dups d
            WHERE sab.{col} = d.artist_uuid;
        """))

    # 2. Deduplicate rows in bridges
    conn.execute(sa.text(
        "DELETE FROM album_artist_bridge a USING album_artist_bridge b WHERE a.ctid < b.ctid AND a.album_uuid = b.album_uuid AND a.artist_uuid = b.artist_uuid"))
    conn.execute(sa.text(
        "DELETE FROM album_release_artist_bridge a USING album_release_artist_bridge b WHERE a.ctid < b.ctid AND a.album_release_uuid = b.album_release_uuid AND a.artist_uuid = b.artist_uuid"))
    conn.execute(sa.text(
        "DELETE FROM track_artist_bridge a USING track_artist_bridge b WHERE a.ctid < b.ctid AND a.track_uuid = b.track_uuid AND a.artist_uuid = b.artist_uuid"))
    conn.execute(sa.text(
        "DELETE FROM track_version_extra_artist a USING track_version_extra_artist b WHERE a.ctid < b.ctid AND a.track_version_uuid = b.track_version_uuid AND a.artist_uuid = b.artist_uuid"))
    conn.execute(sa.text(
        "DELETE FROM artist_tag_bridge a USING artist_tag_bridge b WHERE a.ctid < b.ctid AND a.artist_uuid = b.artist_uuid AND a.tag_uuid = b.tag_uuid"))
    conn.execute(sa.text(
        "DELETE FROM similar_artist_bridge a USING similar_artist_bridge b WHERE a.ctid < b.ctid AND a.reference_artist_uuid = b.reference_artist_uuid AND a.artist_uuid = b.artist_uuid"))

    # 3. Remove duplicate artists themselves (keep rn = 1)
    conn.execute(sa.text("""
        DELETE FROM artist a
        USING (
            SELECT artist_uuid
            FROM (
                SELECT artist_uuid,
                       ROW_NUMBER() OVER (
                           PARTITION BY musicbrainz_artist_id
                           ORDER BY created_at ASC
                       ) AS rn
                FROM artist
                WHERE musicbrainz_artist_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        ) dups
        WHERE a.artist_uuid = dups.artist_uuid;
    """))

    # 4. Add unique constraint
    with op.batch_alter_table('artist', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_artist_mbid', ['musicbrainz_artist_id'])

    with op.batch_alter_table('playback_session', schema=None) as batch_op:
        batch_op.drop_index('ix_playback_session_user_uuid')


def downgrade() -> None:
    with op.batch_alter_table('playback_session', schema=None) as batch_op:
        batch_op.create_index('ix_playback_session_user_uuid', ['user_uuid'], unique=False)

    with op.batch_alter_table('artist', schema=None) as batch_op:
        batch_op.drop_constraint('uq_artist_mbid', type_='unique')
