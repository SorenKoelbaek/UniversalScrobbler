import logging
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=["settings.toml","secrets.toml"],
    load_dotenv=True,
    environments=True,
)

log_level = logging.WARNING
if settings.LOCAL == 'true':
    log_level = logging.INFO


def setup_logging():
    log_level = logging.INFO if settings.LOCAL == 'true' else logging.WARNING

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # 🌍 Global root logger
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [handler]

    # 🎯 Silence specific noisy loggers
    noisy_loggers = [
        "sqlalchemy",              # Base
        "sqlalchemy.engine",       # Queries
        "sqlalchemy.pool",         # Connections
        "sqlalchemy.dialects",     # Driver-level stuff
        "sqlalchemy.orm",          # ORM internals
        "alembic",                 # Migration logs
    ]

    for name in noisy_loggers:
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.handlers = [handler]
        logger.propagate = False

    # ⚙️ FastAPI / Starlette / Uvicorn loggers
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "starlette"]:
        logger = logging.getLogger(name)
        logger.setLevel(log_level)
        logger.handlers = [handler]
        logger.propagate = False

setup_logging()
