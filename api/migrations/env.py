from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from config import settings
from dependencies.database import get_sync_engine
# Import your SQLAlchemy models
from models import sqlmodels

# Alembic Config object
config = context.config

# File configuration for Python logging
fileConfig(config.config_file_name)

# Set target metadata for Alembic migrations
target_metadata = sqlmodels.SQLModel.metadata

_LOCAL = settings.get("LOCAL")

# --- 🛠️ Custom: Skip tables with info={"skip_autogenerate": True} ---

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        if object.info.get("skip_autogenerate", False):
            return False
    return True

def run_migrations(local: bool) -> None:
    """Run migrations in the corresponding environment.

    Args:
        local (bool): Specifies whether it should return a local database.
    """
    connectable = get_sync_engine(local)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
            include_object=include_object,  # 🆕 Added here
        )

        with context.begin_transaction():
            context.run_migrations()


if _LOCAL:
    run_migrations(True)
else:
    run_migrations(False)
