# dependencies/musicbrainz_api.py

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

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS, timeout=15.0)

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}"
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def search_recording_and_return_release_id(
            self, track: str, artist: str, release: Optional[str] = None, favor_album: bool = True
    ) -> Optional[str]:
        """
        Search for a recording and return the release_id (from MusicBrainz) of the
        first *official* release sorted by earliest date. Optionally favor album-type releases.
        """
        if not release:
            query = f'recording:"{track}" AND artist:"{artist}"'
        else:
            query = f'recording:{track} AND artist:{artist}'
            if release:
                query += f' AND release:{release}'

        params = {
            "query": query,
            "fmt": "json",
            "limit": 25,
            "inc": "releases"
        }

        try:
            response = await self.client.get(f"{self.BASE_URL}/recording", params=params)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"❌ MusicBrainz recording search failed: {e}")
            return None

        data = response.json()
        official_releases = []

        for recording in data.get("recordings", []):
            for rel in recording.get("releases", []):
                rg = rel.get("release-group")
                if rel.get("status") != "Official" or not rg:
                    continue

                date_str = rel.get("date") or "9999-12-31"
                # Parse into real date for sorting
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

                official_releases.append({
                    "id": rel.get("id"),
                    "title": rel.get("title"),
                    "date": parsed_date,
                    "release_group_primary_type": rg.get("primary-type"),
                })

        if not official_releases:
            return None

        # Sort all official releases by real parsed date
        official_releases.sort(key=lambda r: r["date"])

        if favor_album:
            for r in official_releases:
                if r.get("release_group_primary_type") == "Album":
                    return r["id"]

        # Fallback: just return the oldest official release
        return official_releases[0]["id"]

    async def get_first_release_id_by_artist_and_album(
            self, artist: str, album: str, favor_album: bool = True
    ) -> Optional[str]:
        """
        Fetch the first official release ID from a release group matching the artist and album title.
        If favor_album is True, prioritizes release-groups with primary-type 'Album'.
        """
        query = f"artistname:{artist} AND release:{album}"
        params = {
            "query": query,
            "inc": "releases",
            "limit": 10,
            "fmt": "json"
        }

        try:
            data = await self._get("release-group", params)
            release_groups = data.get("release-groups", [])
            if not release_groups:
                return None

            # Optionally prioritize Album-type groups
            if favor_album:
                release_groups.sort(
                    key=lambda g: 0 if g.get("primary-type") == "Album" else 1
                )

            for group in release_groups:
                releases = group.get("releases", [])
                if not releases:
                    continue

                # Sort releases by date
                sorted_releases = sorted(
                    releases,
                    key=lambda r: r.get("date") or "9999-99-99"
                )

                # Return the first 'official' one
                for release in sorted_releases:
                    if release.get("status", "").lower() == "official":
                        return release.get("id")

                # Fallback to first non-official release
                return sorted_releases[0].get("id")

        except Exception as e:
            logger.error(f"Error fetching release ID for {artist} - {album}: {e}")

        return None

    async def search_release_group(
        self,
        artist: str,
        release: str,
        limit: int = 5
    ) -> dict:
        query = f"artistname:{artist} AND release:{release}"
        params = {
            "query": query,
            "inc": "releases",
            "limit": limit,
            "fmt": "json"
        }
        return await self._get("release-group", params)

    async def get_release_group_by_release_id(self, release_id: str) -> Optional[dict]:
        url = f"https://musicbrainz.org/ws/2/release-group"
        params = {
            "query": f"reid:{release_id}",
            "fmt": "json"
        }

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        release_groups = data.get("release-groups", [])
        if not release_groups:
            return None
        return release_groups[0]


    async def get_release(self, release_id: str) -> dict:
        url = f"{self.BASE_URL}/release/{release_id}?inc=release-groups"
        params = {
            "inc": "recordings+tags+genres",  # include tracklist, tags, genres
            "fmt": "json"
        }

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def get_recordings_for_release(self, release_id: str) -> list[dict]:
        url = f"{self.BASE_URL}/recording"
        params = {
            "query": f"reid:{release_id}",
            "fmt": "json",
            "inc": "tags",
            "limit": 100
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        recordings = []

        for rec in data.get("recordings", []):
            recordings.append({
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
                # include other fields if you need them later
            })

        return recordings

    async def get_release_by_discogs_url(self, discogs_release_id: int) -> Optional[str]:
        """
        Looks up a MusicBrainz release UUID based on a Discogs release ID.
        """
        url = f"{self.BASE_URL}/url"
        params = {
            "query": f"url:https://www.discogs.com/release/{discogs_release_id}",
            "fmt": "json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        try:
            relations = data["urls"][0]["relation-list"][0]["relations"]
            for rel in relations:
                if rel.get("release"):
                    return rel["release"]["id"]
        except (KeyError, IndexError):
            return None

        return None


# Create a singleton instance
musicbrainz_api = MusicBrainzAPI()
