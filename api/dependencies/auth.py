from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from config import settings
from models.sqlmodels import User
from dependencies.database import get_async_session, get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from passlib.context import CryptContext
import uuid
from sqlalchemy.orm import selectinload

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


# Async version for WebSocket
async def get_current_user_ws(websocket: WebSocket) -> User:
    token = websocket.query_params.get("token")
    if not token:
        print("❌ Missing token in WebSocket request")
        await websocket.close(code=4401)
        return

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid = uuid.UUID(payload.get("sub"))
    except (JWTError, ValueError) as e:
        print("❌ JWT decode error:", e)
        await websocket.close(code=4401)
        return

    engine = get_async_engine()
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.exec(select(User).where(User.user_uuid == user_uuid))
        user = result.first()

        if not user:
            print("❌ No user found for UUID:", user_uuid)
            await websocket.close(code=4403)
            return

        return user


# Async version for HTTP routes
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_async_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid = uuid.UUID(payload.get("sub"))
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.exec(select(User).where(User.user_uuid == user_uuid).options(selectinload(User.spotify_token)))
    user = result.first()
    if user is None:
        raise credentials_exception

    return user


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Password helpers
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def create_user(db: AsyncSession, username: str, email: str, password: str, status: str = "active") -> User:
    """Create a new user."""
    hashed_password = hash_password(password)
    user = User(username=username, email=email, password=hashed_password, status=status)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
