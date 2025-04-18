"""Fix

Revision ID: c29204b33d1d
Revises: 5a33bd400f7d
Create Date: 2025-04-05 22:35:31.847169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c29204b33d1d'
down_revision: Union[str, None] = '5a33bd400f7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('playback_history', sa.Column('track_version_uuid', sa.Uuid(), nullable=True))
    op.create_foreign_key(None, 'playback_history', 'track_version', ['track_version_uuid'], ['track_version_uuid'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'playback_history', type_='foreignkey')
    op.drop_column('playback_history', 'track_version_uuid')
    # ### end Alembic commands ###
