# dependencies/listenbrainz_hov.py

import asyncio
import httpx
from typing import Optional
from config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ListenBrainzAPI:
    BASE_URL = "https://labs.api.listenbrainz.org"
    HEADERS = {
        "User-Agent": f"{settings.get('APPNAME')}/{settings.get('APP_VERSION')} ( soren@sorenkoelbaek.com )"
    }

    def __init__(self, max_retries: int = 3, min_delay: float = 1.0):
        self.client = httpx.AsyncClient(headers=self.HEADERS, timeout=15.0)
        self.max_retries = max_retries
        self.min_delay = min_delay
        self._last_request = 0.0

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.BASE_URL}/{endpoint}/json"

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

    async def get_similar_artist(
        self, artist_mbid: str
    ) -> Optional[str]:
        algorithm = "session_based_days_7500_session_300_contribution_5_threshold_10_limit_100_filter_True_skip_30"
        params = {"artist_mbids": artist_mbid, "algorithm": "algorithm"}

        try:
            data = await self._get("similar-artists", params)
        except httpx.HTTPError as e:
            logger.error(f"❌ ListenBrainz similar artist lookup failed {e}")
            return None


        similar_releases = []
        for artist in data:
                similar_releases.append(
                    {
                        "artist_mbid": artist.get("artist_mbid"),
                        "name": artist.get("name"),
                        "comment": artist.get("comment"),
                        "type": artist.get("type"),
                        "gender": artist.get("gender"),
                        "score": artist.get("score"),
                        "reference_mbid": artist.get("reference_mbid")
                    }
                )

        return similar_releases

# Create a singleton instance
listenbrainz_api = ListenBrainzAPI()
