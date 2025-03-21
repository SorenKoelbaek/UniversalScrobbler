from sqlmodel import SQLModel, Field
from sqlalchemy import func

from uuid import UUID, uuid4
from datetime import datetime

class User(SQLModel, table=True):
    """SQL representation of a user."""
    __tablename__ = "appuser"

    user_uuid: UUID = Field(
        primary_key=True,
        default_factory=uuid4,
        sa_column_kwargs={"unique": True, "server_default": func.gen_random_uuid()},
    )
    username: str
    status: str
    email: str
    created_at: datetime = Field(sa_column_kwargs={"server_default": func.now()})
    password: str