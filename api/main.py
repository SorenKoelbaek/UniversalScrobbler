from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from routers import (auth_router, spotify)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from routers import consumption

import os

app = FastAPI(docs_url="/docs", redoc_url=None, openapi_url="/openapi.json")

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