"""Mark canonical tracks for non-duplicate albums

Revision ID: 4a7c5c23d9b8
Revises: 15beb045667b
Create Date: 2025-04-27 14:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '4a7c5c23d9b8'
down_revision: Union[str, None] = '15beb045667b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Recreate dupe_track_albums temp table
    op.execute("""
        CREATE TEMP TABLE dupe_track_albums AS
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
            COUNT(*) > COUNT(DISTINCT tab.track_number);
    """)

    # Step 2: Mark all tracks not in dupe albums as canonical
    op.execute("""
        UPDATE track_album_bridge tab
        SET canonical_first = TRUE
        WHERE tab.album_uuid NOT IN (
            SELECT album_uuid FROM dupe_track_albums
        );
    """)


def downgrade() -> None:
    # Step 1: Recreate dupe_track_albums again (needed for rollback)
    op.execute("""
        CREATE TEMP TABLE dupe_track_albums AS
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
            COUNT(*) > COUNT(DISTINCT tab.track_number);
    """)

    # Step 2: Revert the canonical_first flags for non-duplicate albums
    op.execute("""
        UPDATE track_album_bridge tab
        SET canonical_first = FALSE
        WHERE tab.album_uuid NOT IN (
            SELECT album_uuid FROM dupe_track_albums
        );
    """)
