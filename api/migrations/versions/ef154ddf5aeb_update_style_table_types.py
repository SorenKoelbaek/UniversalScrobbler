"""update Style table types

Revision ID: ef154ddf5aeb
Revises: 9d992c510f3a
Create Date: 2025-04-29 22:36:05.835634
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ef154ddf5aeb'
down_revision: Union[str, None] = '9d992c510f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop all foreign keys before altering types
    op.drop_constraint("style_style_parent_uuid_fkey", "style", type_="foreignkey")
    op.drop_constraint("style_style_mapping_from_style_uuid_fkey", "style_style_mapping", type_="foreignkey")
    op.drop_constraint("style_style_mapping_to_style_uuid_fkey", "style_style_mapping", type_="foreignkey")

    # Alter UUID-related columns
    op.execute("""
        ALTER TABLE style 
        ALTER COLUMN style_uuid 
        TYPE UUID 
        USING style_uuid::uuid;
    """)
    op.execute("""
        ALTER TABLE style 
        ALTER COLUMN style_parent_uuid 
        TYPE UUID 
        USING style_parent_uuid::uuid;
    """)
    op.execute("""
        ALTER TABLE style_style_mapping 
        ALTER COLUMN from_style_uuid 
        TYPE UUID 
        USING from_style_uuid::uuid;
    """)
    op.execute("""
        ALTER TABLE style_style_mapping 
        ALTER COLUMN to_style_uuid 
        TYPE UUID 
        USING to_style_uuid::uuid;
    """)

    # Re-create foreign keys
    op.create_foreign_key(
        "style_style_parent_uuid_fkey",
        "style", "style",
        ["style_parent_uuid"], ["style_uuid"]
    )
    op.create_foreign_key(
        "style_style_mapping_from_style_uuid_fkey",
        "style_style_mapping", "style",
        ["from_style_uuid"], ["style_uuid"]
    )
    op.create_foreign_key(
        "style_style_mapping_to_style_uuid_fkey",
        "style_style_mapping", "style",
        ["to_style_uuid"], ["style_uuid"]
    )


def downgrade() -> None:
    op.drop_constraint("style_style_mapping_to_style_uuid_fkey", "style_style_mapping", type_="foreignkey")
    op.drop_constraint("style_style_mapping_from_style_uuid_fkey", "style_style_mapping", type_="foreignkey")
    op.drop_constraint("style_style_parent_uuid_fkey", "style", type_="foreignkey")

    op.execute("""
        ALTER TABLE style_style_mapping 
        ALTER COLUMN to_style_uuid 
        TYPE VARCHAR 
        USING to_style_uuid::text;
    """)
    op.execute("""
        ALTER TABLE style_style_mapping 
        ALTER COLUMN from_style_uuid 
        TYPE VARCHAR 
        USING from_style_uuid::text;
    """)
    op.execute("""
        ALTER TABLE style 
        ALTER COLUMN style_parent_uuid 
        TYPE VARCHAR 
        USING style_parent_uuid::text;
    """)
    op.execute("""
        ALTER TABLE style 
        ALTER COLUMN style_uuid 
        TYPE VARCHAR 
        USING style_uuid::text;
    """)

    # Re-create original foreign keys
    op.create_foreign_key(
        "style_style_parent_uuid_fkey",
        "style", "style",
        ["style_parent_uuid"], ["style_uuid"]
    )
    op.create_foreign_key(
        "style_style_mapping_from_style_uuid_fkey",
        "style_style_mapping", "style",
        ["from_style_uuid"], ["style_uuid"]
    )
    op.create_foreign_key(
        "style_style_mapping_to_style_uuid_fkey",
        "style_style_mapping", "style",
        ["to_style_uuid"], ["style_uuid"]
    )
