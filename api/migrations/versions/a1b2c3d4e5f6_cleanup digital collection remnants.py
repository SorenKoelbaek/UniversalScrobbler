"""cleanup digital collection remnants

Revision ID: a1b2c3d4e5f6
Revises: 10f1f470c812
Create Date: 2025-09-09 20:42:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '10f1f470c812'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove digital formats from collections
    op.execute("DELETE FROM collection_album_format WHERE format = 'digital'")

    # Remove dangling collection_album_release_bridge rows (no album_format left for that album/collection)
    op.execute("""
        DELETE FROM collection_album_release_bridge car
        WHERE NOT EXISTS (
            SELECT 1
            FROM collection_album_format caf
            WHERE caf.album_uuid = (
                SELECT album_uuid FROM album_release ar WHERE ar.album_release_uuid = car.album_release_uuid
            )
            AND caf.collection_uuid = car.collection_uuid
        )
    """)

    # Remove dangling collection_album_bridge rows (no album_format left for that album/collection)
    op.execute("""
        DELETE FROM collection_album_bridge cab
        WHERE NOT EXISTS (
            SELECT 1
            FROM collection_album_format caf
            WHERE caf.album_uuid = cab.album_uuid
            AND caf.collection_uuid = cab.collection_uuid
        )
    """)


def downgrade() -> None:
    # ⚠️ Cannot restore deleted data
    # We'll just leave a placeholder so the migration is reversible syntactically.
    # Downgrade will be a no-op.
    pass
