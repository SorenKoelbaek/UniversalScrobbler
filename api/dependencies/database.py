# -*- coding: utf-8 -*-
"""Dependencies for Database.

Module for database dependencies, including methods for returning:
	* RDS client based on assumed role.
	* Database engine, with the possibility of returning a local instance.
	* Returning the database session (for use with routers).
	* method for setting the inherent cache.

"""

import ssl
import urllib.parse
from uuid import uuid4

from config import settings
from sqlalchemy.future import Engine
from sqlmodel import Session, create_engine
from sqlmodel.sql.expression import Select, SelectOfScalar

_local = settings.get("LOCAL")
_db_user = settings.get("USER")
_db_port = settings.get("PORT")
_db_host = settings.get("ENDPOINT")
_db_name = settings.get("DB_NAME")
_db_pass = settings.get("DB_PASS")
_local_postgres_connect_string = (
	f"postgresql+pg8000://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
)


def _get_engine(local: bool) -> Engine:
	"""Return Engine for Database.

	Args:
		local (bool): Specifies if it should return a local database.

	Returns:
		Engine (SQLModel._engine.Engine): Database engine.

	"""
	db_url = _local_postgres_connect_string
	engine = create_engine(db_url, echo=False)

	return engine


def get_session():
	"""Return Database Session.

	Yield:
		Session (sqlmodel.session.Session): Database session.
	"""
	engine = _get_engine(_local)

	with Session(engine) as session:
		yield session


def set_inherit_cache():
	"""Set inherit cache."""
	# https://github.com/tiangolo/sqlmodel/issues/189#issuecomment-1065790432
	SelectOfScalar.inherit_cache = True  # type: ignore
	Select.inherit_cache = True  # type: ignore
