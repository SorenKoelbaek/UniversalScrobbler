
import ssl
import aiohttp
from functools import lru_cache
from typing import Optional
from config import settings
import logging
from config import settings
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://coverartarchive.org"

class CoverArtArchiveAPI:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10)

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)

        return self.session

    async def get_by_release_group(self, release_group_id: str) -> Optional[dict]:
        return await self._fetch(f"/release-group/{release_group_id}")

    async def get_by_release(self, release_id: str) -> Optional[dict]:
        return await self._fetch(f"/release/{release_id}")

    async def _fetch(self, endpoint: str) -> Optional[dict]:
        url = f"{BASE_URL}{endpoint}"
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    logger.info(f"🎨 No cover art found for {endpoint}")
                    return None
                else:
                    logger.warning(f"⚠️ Unexpected response {resp.status} from {url}")
                    return None
        except Exception as e:
            logger.exception(f"❌ Failed to fetch from Cover Art Archive: {e}")
            return None

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

@lru_cache
def get_cover_art_archive_client() -> CoverArtArchiveAPI:
    return CoverArtArchiveAPI()
