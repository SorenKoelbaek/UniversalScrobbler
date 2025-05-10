import os
import sys
import json
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


# --- Path Fix
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Local imports
from dependencies.database import get_async_session
from services.playback_history_service import PlaybackHistoryService
from models.sqlmodels import User


# --- Configuration
USERNAME = "sorenkoelbaek"  # Replace with your real username
JSON_FILE = os.path.join(script_dir, "lastfm_history.json")



def load_lastfm_history_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Flatten [[{}, {}, ...], [{}, {}, ...], ...] → [{}, {}, ...]
    if isinstance(raw, list) and all(isinstance(sub, list) for sub in raw):
        return [entry for sublist in raw for entry in sublist]

    return raw  # already flat


async def import_lastfm_history(session: AsyncSession, json_path: str, user_uuid: str):
    user = User(user_uuid=user_uuid)
    playback_service = PlaybackHistoryService(session)

    history = load_lastfm_history_json(json_path)
    print(f"📄 Loaded {len(history)} Last.fm scrobbles")

    imported, skipped = 0, 0

    for entry in history:
        try:
            artist_name = entry.get("artist", {}).get("#text", "").strip()
            track_name = entry.get("name", "").strip()
            album_name = entry.get("album", {}).get("#text", "").strip()
            album_mbid = entry.get("album", {}).get("mbid") or None
            timestamp = entry.get("date", {}).get("uts")

            if not artist_name or not track_name or not timestamp:
                skipped += 1
                continue

            played_at = datetime.utcfromtimestamp(int(timestamp)).replace(tzinfo=timezone.utc)

            success = await playback_service.add_historic_listen(
                user=user,
                artist_name=artist_name,
                track_name=track_name,
                album_name=album_name or None,
                played_at=played_at,
                source="lastfm",
                album_mbid=album_mbid or None,
            )

            if success:
                imported += 1
            else:
                skipped += 1

            if imported % 50 == 0:
                await session.commit()
                print(f"✅ Committed {imported} entries...")

        except Exception as e:
            print(f"⚠️ Failed to process entry: {entry.get('name')} — {e}")
            skipped += 1

    await session.commit()
    print(f"🎉 Import finished. Imported: {imported}, Skipped: {skipped}")

async def get_user_by_username(session: AsyncSession, username: str) -> User:
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"❌ User not found: {username}")
    return user

async def main():
    async for session in get_async_session():
        user = await get_user_by_username(session, USERNAME)
        await import_lastfm_history(session, JSON_FILE, user.user_uuid)


if __name__ == "__main__":
    asyncio.run(main())
