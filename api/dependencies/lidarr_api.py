# dependencies/Lidarr_api.py
"""This module provides an asynchronous API Client for interacting with the Lidarr API, the intent is to automatically an artist's MBID."""
import asyncio
import httpx
from typing import Optional
from config import settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class LidarrApi:
    BASE_URL = "https://192.168.0.16:8686"
    HEADERS = {
        "User-Agent": f"{settings.get('APPNAME')}/{settings.get('APP_VERSION')} ( soren@sorenkoelbaek.com )"
    }
    def __init__(self, max_retries: int = 3, min_delay: float = 0.2):
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
                        f"503 from LidarrAPI, retry {attempt+1}/{self.max_retries} in {backoff}s: {url}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise

lidarr_api = LidarrApi()
