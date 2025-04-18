"""added collection models

Revision ID: fafa2cdeb6b2
Revises: 990e11fa021b
Create Date: 2025-03-28 20:02:17.787904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'fafa2cdeb6b2'
down_revision: Union[str, None] = '990e11fa021b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('album',
    sa.Column('album_uuid', sa.Uuid(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('discogs_release_id', sa.Integer(), nullable=True),
    sa.Column('styles', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('country', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('album_uuid')
    )
    op.create_table('artist',
    sa.Column('artist_uuid', sa.Uuid(), nullable=False),
    sa.Column('discogs_artist_id', sa.Integer(), nullable=True),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name_variations', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('profile', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('artist_uuid')
    )
    op.create_table('album_artist_bridge',
    sa.Column('album_uuid', sa.Uuid(), nullable=False),
    sa.Column('artist_uuid', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['album_uuid'], ['album.album_uuid'], ),
    sa.ForeignKeyConstraint(['artist_uuid'], ['artist.artist_uuid'], ),
    sa.PrimaryKeyConstraint('album_uuid', 'artist_uuid')
    )
    op.create_table('artist_bridge',
    sa.Column('parent_artist_uuid', sa.Uuid(), nullable=False),
    sa.Column('child_artist_uuid', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['child_artist_uuid'], ['artist.artist_uuid'], ),
    sa.ForeignKeyConstraint(['parent_artist_uuid'], ['artist.artist_uuid'], ),
    sa.PrimaryKeyConstraint('parent_artist_uuid', 'child_artist_uuid')
    )
    op.create_table('collection',
    sa.Column('collection_uuid', sa.Uuid(), nullable=False),
    sa.Column('collection_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_uuid', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_uuid'], ['appuser.user_uuid'], ),
    sa.PrimaryKeyConstraint('collection_uuid')
    )
    op.create_table('discogs_track',
    sa.Column('track_uuid', sa.Uuid(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('album_uuid', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['album_uuid'], ['album.album_uuid'], ),
    sa.PrimaryKeyConstraint('track_uuid')
    )
    op.create_table('collection_album_bridge',
    sa.Column('album_uuid', sa.Uuid(), nullable=False),
    sa.Column('collection_uuid', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['album_uuid'], ['album.album_uuid'], ),
    sa.ForeignKeyConstraint(['collection_uuid'], ['collection.collection_uuid'], ),
    sa.PrimaryKeyConstraint('album_uuid', 'collection_uuid')
    )
    op.add_column('playback_history', sa.Column('track_uuid', sa.Uuid(), nullable=True))
    op.add_column('playback_history', sa.Column('artist_uuid', sa.Uuid(), nullable=True))
    op.add_column('playback_history', sa.Column('album_uuid', sa.Uuid(), nullable=True))
    op.alter_column('playback_history', 'playback_history_uuid',
               existing_type=sa.UUID(),
               server_default=None,
               existing_nullable=False)
    op.drop_constraint('playback_history_playback_history_uuid_key', 'playback_history', type_='unique')
    op.create_foreign_key(None, 'playback_history', 'artist', ['artist_uuid'], ['artist_uuid'])
    op.create_foreign_key(None, 'playback_history', 'discogs_track', ['track_uuid'], ['track_uuid'])
    op.create_foreign_key(None, 'playback_history', 'album', ['album_uuid'], ['album_uuid'])
    op.drop_column('playback_history', 'discogs_release_id')
    op.drop_column('playback_history', 'track_name')
    op.drop_column('playback_history', 'album_name')
    op.drop_column('playback_history', 'artist_name')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('playback_history', sa.Column('artist_name', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('playback_history', sa.Column('album_name', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('playback_history', sa.Column('track_name', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('playback_history', sa.Column('discogs_release_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'playback_history', type_='foreignkey')
    op.drop_constraint(None, 'playback_history', type_='foreignkey')
    op.drop_constraint(None, 'playback_history', type_='foreignkey')
    op.create_unique_constraint('playback_history_playback_history_uuid_key', 'playback_history', ['playback_history_uuid'])
    op.alter_column('playback_history', 'playback_history_uuid',
               existing_type=sa.UUID(),
               server_default=sa.text('gen_random_uuid()'),
               existing_nullable=False)
    op.drop_column('playback_history', 'album_uuid')
    op.drop_column('playback_history', 'artist_uuid')
    op.drop_column('playback_history', 'track_uuid')
    op.drop_table('collection_album_bridge')
    op.drop_table('discogs_track')
    op.drop_table('collection')
    op.drop_table('artist_bridge')
    op.drop_table('album_artist_bridge')
    op.drop_table('artist')
    op.drop_table('album')
    # ### end Alembic commands ###
