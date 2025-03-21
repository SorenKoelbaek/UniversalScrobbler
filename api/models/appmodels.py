from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    """Base model for a user."""
    username: str
    email: str
    status: Optional[str] = None


class UserRead(UserBase):
    """Model for reading user details."""
    user_uuid: UUID

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

