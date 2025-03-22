from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from dependencies.database import get_session
from dependencies.auth import create_access_token, get_current_user, verify_password, create_user
from models.sqlmodels import User
from models.appmodels import UserRead, UserCreate
from datetime import timedelta
from uuid import UUID
router = APIRouter()

@router.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": str(user.user_uuid)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh-token")
def refresh_token(
    user: User = Depends(get_current_user), db: Session = Depends(get_session)
):
    # Generate a new token for the user
    access_token = create_access_token(data={"sub": str(user.user_uuid)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
def get_current_user(user: User = Depends(get_current_user)):
    """Get the current user's details, including the preferred garden."""
    return user  # SQLModel will automatically resolve relationships


@router.post("/users/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
        user_in: UserCreate,
        session: Session = Depends(get_session),
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
