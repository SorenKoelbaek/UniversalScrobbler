from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session
from dependencies.database import get_session
from models.sqlmodels import User
import uuid
from passlib.context import CryptContext
from config import settings


# Initialize the password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# JWT configuration
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# Create access token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Get current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid: str = payload.get("sub")
        if user_uuid is None:
            raise credentials_exception
        token_data = uuid.UUID(user_uuid)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.user_uuid == token_data).first()
    if user is None:
        raise credentials_exception
    return user

def create_user(db: Session, username: str, email: str, password: str, status: str = "active"):
    """Create a new user."""
    hashed_password = hash_password(password)
    user = User(username=username, email=email, password=hashed_password, status=status)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def hash_password(password: str) -> str:
    """Hash a plain text password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)