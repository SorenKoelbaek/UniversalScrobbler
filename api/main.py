from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from routers import (auth_router, spotify)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routers import consumption
from config import settings
import asyncio
from scripts.gather_playback import gather_all_playbacks
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
app.include_router(auth_router.router)
app.include_router(spotify.router)
app.include_router(consumption.router)

logging.info(f"Starting with environment = {settings.current_env}")

@app.on_event("startup")
async def startup_event():
    if settings.LOCAL == "true":
        # Run the gatherer in the background on app startup (dev mode)
        asyncio.create_task(run_gatherer())

async def run_gatherer():
    while True:  # This will make it run forever in a loop
        try:
            logger.info("[GATHERER] Starting gather task...")
            await asyncio.to_thread(gather_all_playbacks)  # Run gather in a separate thread
            logger.info("[GATHERER] Playback history gathered successfully.")
        except Exception as e:
            logger.error(f"[GATHERER] Error during gathering: {e}")

        # Wait for 10 minutes before running the task again
        await asyncio.sleep(600)  # 600 seconds = 10 minutes