"""fixed foreign key constrant

Revision ID: 0fe4eea4193e
Revises: f44f6e177002
Create Date: 2025-09-16 13:26:13.027720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0fe4eea4193e'
down_revision: Union[str, None] = 'f44f6e177002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing FK
    op.drop_constraint(
        "playback_session_current_queue_uuid_fkey",
        "playback_session",
        type_="foreignkey",
    )

    # Recreate with ON DELETE SET NULL
    op.create_foreign_key(
        "playback_session_current_queue_uuid_fkey",
        source_table="playback_session",
        referent_table="playback_queue",
        local_cols=["current_queue_uuid"],
        remote_cols=["playback_queue_uuid"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the modified FK
    op.drop_constraint(
        "playback_session_current_queue_uuid_fkey",
        "playback_session",
        type_="foreignkey",
    )

    # Recreate the original strict FK
    op.create_foreign_key(
        "playback_session_current_queue_uuid_fkey",
        source_table="playback_session",
        referent_table="playback_queue",
        local_cols=["current_queue_uuid"],
        remote_cols=["playback_queue_uuid"],
    )