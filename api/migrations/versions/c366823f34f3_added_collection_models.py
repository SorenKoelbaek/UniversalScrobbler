"""added collection models

Revision ID: c366823f34f3
Revises: 5c9b6eec8205
Create Date: 2025-03-28 21:23:09.573395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c366823f34f3'
down_revision: Union[str, None] = '5c9b6eec8205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('discogs_oauth_temp',
    sa.Column('oauth_token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('oauth_token_secret', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_uuid', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_uuid'], ['appuser.user_uuid'], ),
    sa.PrimaryKeyConstraint('oauth_token')
    )
    op.create_unique_constraint(None, 'discogs_token', ['discogs_token_uuid'])
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'discogs_token', type_='unique')
    op.drop_table('discogs_oauth_temp')
    # ### end Alembic commands ###
