from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select
from datetime import datetime, timedelta, UTC
from dependencies.auth import get_current_user
from dependencies.database import get_session
from models.sqlmodels import PlaybackHistory, User
from models.appmodels import PlaybackHistoryRead
from typing import List
from collections import Counter


router = APIRouter(
    prefix="/consumption",
    tags=["consumption"],
)


@router.get("/top-tracks")
def get_top_tracks(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    since = datetime.utcnow() - timedelta(days=days)

    results = db.exec(
        select(PlaybackHistory)
        .where(PlaybackHistory.user_uuid == user.user_uuid)
        .where(PlaybackHistory.played_at >= since)
    ).all()

    # Count plays per unique (track, artist, album) triple
    play_counter = Counter(
        (r.track_name, r.artist_name, r.album_name)
        for r in results
    )

    top_tracks = [
        {
            "track_name": t[0],
            "artist_name": t[1],
            "album_name": t[2],
            "play_count": count
        }
        for t, count in play_counter.most_common(10)
    ]

    return top_tracks

@router.get("/history", response_model=List[PlaybackHistoryRead])
def get_consumption_history(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
):
    cutoff = datetime.now(UTC) - timedelta(days=days)

    statement = (
        select(PlaybackHistory)
        .where(PlaybackHistory.user_uuid == user.user_uuid)
        .where(PlaybackHistory.played_at >= cutoff)
        .order_by(PlaybackHistory.played_at.desc())
    )

    return db.exec(statement).all()
