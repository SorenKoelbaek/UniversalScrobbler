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
    log_level = logging.DEBUG


def setup_logging():
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

    # 🛠️ Set the general Uvicorn logger level to respect our log_level
    uvicorn_general = logging.getLogger("uvicorn")
    uvicorn_general.setLevel(log_level)
    uvicorn_general.handlers = [handler]
    uvicorn_general.propagate = False

setup_logging()