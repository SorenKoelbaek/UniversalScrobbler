"""added track filter column

Revision ID: 15beb045667b
Revises: c1d3ea2f5a4b
Create Date: 2025-04-27 12:02:14.107699

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '15beb045667b'
down_revision: Union[str, None] = 'c1d3ea2f5a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add canonical_first column
    op.add_column('track_album_bridge', sa.Column('canonical_first', sa.Boolean(), nullable=False, server_default=sa.false()))

    # Populate canonical_first based on first album releases

    # Step 1: Create temp table first_releases
    op.execute("""
        CREATE TEMP TABLE first_releases AS
        SELECT DISTINCT ON (ar.album_uuid)
            ar.album_uuid,
            ar.album_release_uuid
        FROM
            album_release ar
        WHERE
            ar.album_uuid IN (
                SELECT album_uuid FROM (
                    SELECT
                        tab.album_uuid
                    FROM
                        track_album_bridge tab
                    JOIN (
                        SELECT
                            ar.album_uuid
                        FROM
                            album_release ar
                        GROUP BY
                            ar.album_uuid
                        HAVING
                            COUNT(*) > 1
                            AND SUM(CASE WHEN ar.discogs_release_id IS NOT NULL THEN 1 ELSE 0 END) >= 1
                    ) ar_filtered ON tab.album_uuid = ar_filtered.album_uuid
                    WHERE
                        tab.track_number IS NOT NULL
                    GROUP BY
                        tab.album_uuid
                    HAVING
                        COUNT(*) > COUNT(DISTINCT tab.track_number)
                ) AS dupe_track_albums
            )
            AND ar.discogs_release_id IS NOT NULL
        ORDER BY
            ar.album_uuid,
            ar.release_date ASC NULLS LAST;
    """)

    # Step 2: Create temp table canonical_album_tracks
    op.execute("""
        CREATE TEMP TABLE canonical_album_tracks AS
        SELECT
            tarb.album_uuid,
            t.track_uuid
        FROM
            first_releases fr
        INNER JOIN
            track_version_album_release_bridge tvarb ON tvarb.album_release_uuid = fr.album_release_uuid
        INNER JOIN
            track_version tv ON tv.track_version_uuid = tvarb.track_version_uuid
        INNER JOIN
            track t ON t.track_uuid = tv.track_uuid
        INNER JOIN
            track_album_bridge tarb ON tarb.track_uuid = t.track_uuid
        WHERE
            tarb.album_uuid = fr.album_uuid;
    """)

    # Step 3: Update track_album_bridge to set canonical_first = TRUE
    op.execute("""
        UPDATE track_album_bridge tab
        SET canonical_first = TRUE
        FROM canonical_album_tracks cat
        WHERE
            tab.album_uuid = cat.album_uuid
            AND tab.track_uuid = cat.track_uuid;
    """)


def downgrade() -> None:
    # Drop canonical_first column
    op.drop_column('track_album_bridge', 'canonical_first')
