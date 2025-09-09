from fastapi import FastAPI
from routers import (auth_router, spotify, discogs, music, collection, healtcheck, playback_session, listen)
from fastapi.security import OAuth2PasswordBearer
from routers import event
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from dependencies.auth import get_current_user
from contextlib import asynccontextmanager
from dependencies.redis import init_redis, close_redis
from services.redis_sse_service import redis_sse_service

from config import settings
import logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    redis_sse_service.start()
    try:
        yield
    finally:
        redis_sse_service.stop()
        await close_redis()

logger = logging.getLogger(__name__)
show_docs = settings.LOCAL == "true"


app = FastAPI(
    title="My App",
    docs_url="/docs" if show_docs else None,
    redoc_url="/redoc" if show_docs else None,
    openapi_url="/openapi.json" if show_docs else None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allow Authorization header
)

app.include_router(healtcheck.router)
app.include_router(spotify.router)
app.include_router(discogs.router)
app.include_router(collection.router)
app.include_router(music.router)
app.include_router(playback_session.router)
app.include_router(event.router)
app.include_router(auth_router.router)
app.include_router(listen.router)

logging.info(f"Starting with environment = {settings.current_env}")

