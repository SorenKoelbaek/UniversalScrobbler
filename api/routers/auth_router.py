from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from dependencies.database import get_async_session
from dependencies.auth import create_access_token, get_current_user, verify_password, create_user
from models.sqlmodels import User
from models.appmodels import UserRead, UserCreate
from datetime import timedelta
import secrets
from datetime import datetime
from models.sqlmodels import RefreshToken

router = APIRouter()


@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_async_session)
):
    statement = select(User).where(User.username == form_data.username)
    result = await db.exec(statement)
    user = result.first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": str(user.user_uuid)},
        expires_delta=access_token_expires
    )

    # Create refresh token
    raw_refresh_token = secrets.token_urlsafe(64)
    refresh_token = RefreshToken(
        user_uuid=user.user_uuid,
        token=raw_refresh_token,
    )
    db.add(refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh_token,
        "expires_at": (datetime.utcnow() + access_token_expires).isoformat()
    }

from fastapi import Form, Depends
from sqlmodel import select
from dependencies.database import get_async_session
from models.sqlmodels import RefreshToken
from dependencies.auth import create_access_token
from datetime import datetime, timedelta
import secrets

@router.post("/refresh-token")
async def refresh_token(
    grant_type: str = Form(...),
    refresh_token: str = Form(...),
    db: Session = Depends(get_async_session)
):
    if grant_type != "refresh_token":
        raise HTTPException(status_code=400, detail="Invalid grant_type")

    # Lookup and validate token
    statement = select(RefreshToken).where(
        RefreshToken.token == refresh_token,
        RefreshToken.revoked == False
    )
    result = await db.exec(statement)
    token_entry = result.first()

    if not token_entry:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

    # Revoke old token
    token_entry.revoked = True

    # Generate new access token
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": str(token_entry.user_uuid)},
        expires_delta=access_token_expires
    )

    # Generate new refresh token
    new_raw_token = secrets.token_urlsafe(64)
    new_refresh_token = RefreshToken(
        user_uuid=token_entry.user_uuid,
        token=new_raw_token
    )
    db.add(new_refresh_token)
    await db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_raw_token,
        "token_type": "bearer",
        "expires_at": (datetime.utcnow() + access_token_expires).isoformat()
    }


@router.get("/me", response_model=UserRead)
async def get_current_user(user: User = Depends(get_current_user)):
    """Get the current user's details, including the preferred garden."""
    return user  # SQLModel will automatically resolve relationships

@router.post("/users/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
        user_in: UserCreate,
        session: Session = Depends(get_async_session),
):
    # Check if user already exists
    existing_user = session.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Create user
    user = create_user(
        db=session,
        username=user_in.username,
        email=user_in.email,
        password=user_in.password
    )
    return user
