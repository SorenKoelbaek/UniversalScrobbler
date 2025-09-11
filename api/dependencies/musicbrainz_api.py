# dependencies/musicbrainz_api.py

import asyncio
import httpx
from typing import Optional
from config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class MusicBrainzAPI:
    BASE_URL = "https://musicbrainz.org/ws/2"
    HEADERS = {
        "User-Agent": f"{settings.get('APPNAME')}/{settings.get('APP_VERSION')} ( soren@sorenkoelbaek.com )"
    }

    def __init__(self, max_retries: int = 3, min_delay: float = 1.0):
        self.client = httpx.AsyncClient(headers=self.HEADERS, timeout=15.0)
        self.max_retries = max_retries
        self.min_delay = min_delay
        self._last_request = 0.0

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"

        for attempt in range(self.max_retries):
            # enforce 1 req/sec
            now = asyncio.get_event_loop().time()
            since_last = now - self._last_request
            if since_last < self.min_delay:
                await asyncio.sleep(self.min_delay - since_last)

            try:
                resp = await self.client.get(url, params=params)
                self._last_request = asyncio.get_event_loop().time()
                resp.raise_for_status()
                return resp.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503 and attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"503 from MusicBrainz, retry {attempt+1}/{self.max_retries} in {backoff}s: {url}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise

    async def search_recording_and_return_release_id(
        self, track: str, artist: str, release: Optional[str] = None, favor_album: bool = True
    ) -> Optional[str]:
        if not release:
            query = f'recording:"{track}" AND artist:"{artist}"'
        else:
            query = f'recording:{track} AND artist:{artist} AND release:{release}'

        params = {"query": query, "fmt": "json", "limit": 25, "inc": "releases"}

        try:
            data = await self._get("recording", params)
        except httpx.HTTPError as e:
            logger.error(f"❌ MusicBrainz recording search failed: {e}")
            return None

        official_releases = []
        for recording in data.get("recordings", []):
            for rel in recording.get("releases", []):
                rg = rel.get("release-group")
                if rel.get("status") != "Official" or not rg:
                    continue
                date_str = rel.get("date") or "9999-12-31"
                try:
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m")
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(date_str, "%Y")
                        except ValueError:
                            parsed_date = datetime(9999, 12, 31)
                official_releases.append(
                    {
                        "id": rel.get("id"),
                        "title": rel.get("title"),
                        "date": parsed_date,
                        "release_group_primary_type": rg.get("primary-type"),
                    }
                )

        if not official_releases:
            return None

        official_releases.sort(key=lambda r: r["date"])
        if favor_album:
            for r in official_releases:
                if r.get("release_group_primary_type") == "Album":
                    return r["id"]
        return official_releases[0]["id"]

    async def get_first_release_id_by_artist_and_album(
        self, artist: str, album: str, favor_album: bool = True
    ) -> Optional[str]:
        query = f"artistname:{artist} AND release:{album}"
        params = {"query": query, "inc": "releases", "limit": 10, "fmt": "json"}

        try:
            data = await self._get("release-group", params)
            release_groups = data.get("release-groups", [])
            if not release_groups:
                return None
            if favor_album:
                release_groups.sort(
                    key=lambda g: 0 if g.get("primary-type") == "Album" else 1
                )
            for group in release_groups:
                releases = group.get("releases", [])
                if not releases:
                    continue
                sorted_releases = sorted(
                    releases, key=lambda r: r.get("date") or "9999-99-99"
                )
                for release in sorted_releases:
                    if release.get("status", "").lower() == "official":
                        return release.get("id")
                return sorted_releases[0].get("id")
        except Exception as e:
            logger.error(f"Error fetching release ID for {artist} - {album}: {e}")
        return None

    async def search_release_group(self, artist: str, release: str, limit: int = 5) -> dict:
        query = f"artistname:{artist} AND release:{release}"
        params = {"query": query, "inc": "releases", "limit": limit, "fmt": "json"}
        return await self._get("release-group", params)

    async def get_release_group_by_release_id(self, release_id: str) -> Optional[dict]:
        params = {"query": f"reid:{release_id}", "fmt": "json"}
        data = await self._get("release-group", params)
        release_groups = data.get("release-groups", [])
        if not release_groups:
            return None
        return release_groups[0]

    async def get_release(self, release_id: str) -> dict:
        params = {"inc": "recordings+tags+genres", "fmt": "json"}
        return await self._get(f"release/{release_id}", params)

    async def get_recordings_for_release(self, release_id: str) -> list[dict]:
        params = {"query": f"reid:{release_id}", "fmt": "json", "inc": "tags", "limit": 100}
        data = await self._get("recording", params)
        recordings = []
        for rec in data.get("recordings", []):
            recordings.append(
                {
                    "recording_id": rec.get("id"),
                    "title": rec.get("title"),
                    "length": rec.get("length"),
                    "tags": [
                        {"name": tag["name"], "count": tag.get("count", 0)}
                        for tag in rec.get("tags", [])
                    ],
                    "artist_credits": [
                        {
                            "name": a["name"],
                            "artist_id": a["artist"]["id"],
                            "artist_name": a["artist"]["name"],
                        }
                        for a in rec.get("artist-credit", [])
                    ],
                }
            )
        return recordings

    async def get_release_by_discogs_url(self, discogs_release_id: int) -> Optional[str]:
        url = f"{self.BASE_URL}/url"
        params = {"query": f"url:https://www.discogs.com/release/{discogs_release_id}", "fmt": "json"}
        data = await self._get("url", params)
        try:
            relations = data["urls"][0]["relation-list"][0]["relations"]
            for rel in relations:
                if rel.get("release"):
                    return rel["release"]["id"]
        except (KeyError, IndexError):
            return None
        return None

    async def get_artist(self, artist_mbid: str, include_release_groups: bool = True) -> Optional[dict]:
        """
        Fetch a single artist from MusicBrainz by MBID.
        Optionally include release groups for richer imports.
        """
        inc = "tags+genres"
        if include_release_groups:
            inc += "+release-groups"

        params = {"fmt": "json", "inc": inc}
        try:
            data = await self._get(f"artist/{artist_mbid}", params)
            return data
        except httpx.HTTPError as e:
            logger.error(f"❌ MusicBrainz get_artist failed for {artist_mbid}: {e}")
            return None


# Create a singleton instance
musicbrainz_api = MusicBrainzAPI()
