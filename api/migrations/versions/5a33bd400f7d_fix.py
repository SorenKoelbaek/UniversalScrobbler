"""Fix

Revision ID: 5a33bd400f7d
Revises: 6741246eac76
Create Date: 2025-04-04 16:43:40.203321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5a33bd400f7d'
down_revision: Union[str, None] = '6741246eac76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Replace the automatic type conversion with an explicit SQL command
    op.execute('ALTER TABLE track_version ALTER COLUMN duration TYPE INTEGER USING duration::integer')


def downgrade() -> None:
    # Keep the existing downgrade logic or make it explicit too
    op.execute('ALTER TABLE track_version ALTER COLUMN duration TYPE VARCHAR USING duration::varchar')
