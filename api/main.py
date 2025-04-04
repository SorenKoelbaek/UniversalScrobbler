from fastapi import FastAPI
from routers import (auth_router, database, spotify, consumption, discogs, music, collection)
from routers import event
from fastapi.middleware.cors import CORSMiddleware


import asyncio
from config import settings
import logging


logger = logging.getLogger(__name__)
show_docs = settings.LOCAL == "true"


app = FastAPI(
    title="My App",
    docs_url="/docs" if show_docs else None,
    redoc_url="/redoc" if show_docs else None,
    openapi_url="/openapi.json" if show_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "https://sorenkoelbaek.dk",  # Production domain
        "https://api.sorenkoelbaek.dk",  # FastAPI endpoint for production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*","Authorization"],  # Allow Authorization header
)

app.include_router(spotify.router)
app.include_router(discogs.router)
app.include_router(collection.router)
app.include_router(consumption.router)
app.include_router(music.router)

#app.include_router(event.router)
app.include_router(auth_router.router)
app.include_router(database.router)

logging.info(f"Starting with environment = {settings.current_env}")

