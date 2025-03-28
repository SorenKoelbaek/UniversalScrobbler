"""added Spotify Token to user model

Revision ID: 63e2f1b8c3e7
Revises: ec065c8f086f
Create Date: 2025-03-22 12:34:27.894407

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '63e2f1b8c3e7'
down_revision: Union[str, None] = 'ec065c8f086f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('spotifytoken',
    sa.Column('spotify_token_uuid', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_uuid', sa.Uuid(), nullable=False),
    sa.Column('access_token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('refresh_token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_uuid'], ['appuser.user_uuid'], ),
    sa.PrimaryKeyConstraint('spotify_token_uuid'),
    sa.UniqueConstraint('spotify_token_uuid'),
    sa.UniqueConstraint('user_uuid')
    )
    op.create_unique_constraint(None, 'appuser', ['user_uuid'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'appuser', type_='unique')
    op.drop_table('spotifytoken')
    # ### end Alembic commands ###
