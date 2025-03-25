from fastapi import APIRouter, Depends
from dependencies.auth import get_current_user
from dependencies.database import get_async_session
from services.spotify_service import SpotifyService
from sqlmodel import Session, select
from models.sqlmodels import User
from models.appmodels import SpotifyAuthRequest
from fastapi.responses import RedirectResponse
from dependencies.database import get_async_session

router = APIRouter(
    prefix="/spotify",
    tags=["spotify"]
)

spotify_service = SpotifyService()

@router.get("/login")
def login():
    auth_url = spotify_service.get_redirect_url()
    return RedirectResponse(auth_url)

@router.post("/authorize")
async def authorize_spotify(
    payload: SpotifyAuthRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_async_session)
):
    return spotify_service.add_token_for_user(payload.code, user.user_uuid, db)



@router.get("/playback")
async def get_current_playback(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_async_session),
):
    spotify_service = SpotifyService()
    playback = spotify_service.get_current_playback(user.user_uuid, db)
    return playback

@router.get("/top-tracks")
async def get_top_tracks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_async_session),
    days: int = 7
):
    spotify_service = SpotifyService()
    top_tracks = spotify_service.get_top_tracks(user.user_uuid, db, days)
    return top_tracks

@router.post("/gather-playback")
async def gather_playback_for_user(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_async_session),
    limit: int = 5  # Set default limit to 5
):
    spotify_service = SpotifyService()
    spotify_service.gather_user_playback_history(user.user_uuid, db, limit)
    return {"status": "Playback history gathered"}
