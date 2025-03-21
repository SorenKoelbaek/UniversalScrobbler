
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=["settings.toml","secrets.toml"],
    load_dotenv=True,
    environments=True,
)
