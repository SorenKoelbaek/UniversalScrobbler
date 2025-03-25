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
    log_level = logging.INFO  # or DEBUG if you're actively developing

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [handler]

    # 🛠️ Attach your format to Uvicorn's loggers too
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(log_level)
    uvicorn_access.handlers = [handler]
    uvicorn_access.propagate = False

    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.setLevel(logging.ERROR)
    uvicorn_error.handlers = [handler]
    uvicorn_error.propagate = False

    uvicorn_general = logging.getLogger("uvicorn")
    uvicorn_general.setLevel(log_level)
    uvicorn_general.handlers = [handler]
    uvicorn_general.propagate = False

    # 🧹 Silence noisy SQLAlchemy internals
    sqlalchemy_engine = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_engine.setLevel(logging.WARNING)
    sqlalchemy_engine.handlers = [handler]
    sqlalchemy_engine.propagate = False

    sqlalchemy_pool = logging.getLogger("sqlalchemy.pool")
    sqlalchemy_pool.setLevel(logging.WARNING)
    sqlalchemy_pool.handlers = [handler]
    sqlalchemy_pool.propagate = False

    # Optional: FastAPI internals
    fastapi_logger = logging.getLogger("fastapi")
    fastapi_logger.setLevel(logging.WARNING)
    fastapi_logger.handlers = [handler]
    fastapi_logger.propagate = False

    # Optional: Starlette internals
    starlette_logger = logging.getLogger("starlette")
    starlette_logger.setLevel(logging.WARNING)
    starlette_logger.handlers = [handler]
    starlette_logger.propagate = False

setup_logging()
