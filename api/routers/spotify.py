from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user
from dependencies.database import get_session
from services.spotify_service import SpotifyService
from sqlmodel import Session, select
from models.sqlmodels import User

router = APIRouter(
    prefix="/spotify",
    tags=["spotify"]
)

@router.get("/login")
def login():
    spotify_service = SpotifyService()
    auth_url = spotify_service.login()
    return {"auth_url": auth_url}

@router.post("/authorize")
def authorize_spotify(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    spotify_service = SpotifyService()
    response = spotify_service.authorize(code, user.user_uuid, db)
    return response

@router.get("/playback")
def get_current_playback(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    spotify_service = SpotifyService()
    playback = spotify_service.get_current_playback(user.user_uuid, db)
    return playback

@router.get("/top-tracks")
def get_top_tracks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    days: int = 7
):
    spotify_service = SpotifyService()
    top_tracks = spotify_service.get_top_tracks(user.user_uuid, db, days)
    return top_tracks

@router.post("/gather-playback")
def gather_playback_for_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    limit: int = 5  # Set default limit to 5
):
    spotify_service = SpotifyService()
    spotify_service.gather_user_playback_history(user.user_uuid, db, limit)
    return {"status": "Playback history gathered"}
