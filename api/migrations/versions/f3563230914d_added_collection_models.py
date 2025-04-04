"""added collection models

Revision ID: f3563230914d
Revises: 8d12bf2e3f15
Create Date: 2025-03-29 15:39:41.917403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3563230914d'
down_revision: Union[str, None] = '8d12bf2e3f15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('album', sa.Column('discogs_master_id', sa.Integer(), nullable=True))
    op.add_column('album', sa.Column('discogs_main_release_id', sa.Integer(), nullable=True))
    op.add_column('album_release', sa.Column('is_main_release', sa.Boolean(), nullable=False))
    op.alter_column('appuser', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               server_default=None,
               existing_nullable=False)
    op.create_unique_constraint(None, 'spotify_token', ['spotify_token_uuid'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'spotify_token', type_='unique')
    op.alter_column('appuser', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               server_default=sa.text('now()'),
               existing_nullable=False)
    op.drop_column('album_release', 'is_main_release')
    op.drop_column('album', 'discogs_main_release_id')
    op.drop_column('album', 'discogs_master_id')
    # ### end Alembic commands ###
