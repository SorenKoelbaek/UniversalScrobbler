import time
import requests
from pydantic_core.core_schema import none_schema

from config import settings
from requests_oauthlib import OAuth1Session
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

class DiscogsAPI:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rate_limit_max = 50  # Max requests per minute
            cls._instance.rate_limit_window = 15  # seconds
            cls._instance.requests_made = 0
            cls._instance.last_request_time = []
            cls._instance.base_url = "https://api.discogs.com"
        return cls._instance

    def _rate_limit(self, remaining_calls: int):
        """Rate limit handler that pauses requests based on remaining calls."""
        if remaining_calls <= 10:
            logger.info("Rate limit hit, sleeping for 60 seconds")
            time.sleep(self.rate_limit_window)  # Sleep for the rate limit window time

    def get_collection(self, token: str, secret: str) -> list[dict]:
        """Fetch the full user's collection from Discogs using OAuth1, paginated and rate-limited."""
        identity = self.get_oauth_identity(token, secret)
        if not identity:
            raise Exception("Failed to get user identity")

        username = identity['username']
        oauth = OAuth1Session(
            client_key=settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_SECRET_KEY,
            resource_owner_key=token,
            resource_owner_secret=secret
        )

        all_releases = []
        page = 1
        while True:
            # Request and check rate limit based on response headers
            url = f"{self.base_url}/users/{username}/collection/folders/0/releases?page={page}&per_page=50"
            try:
                response = oauth.get(url)
                response.raise_for_status()  # Raise for other HTTP errors
                data = response.json()
                headers = response.headers
                remaining_calls = int(headers.get("x-discogs-ratelimit-remaining"))
                # Use remaining calls from the response header to handle rate-limiting
                self._rate_limit(remaining_calls)

            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Failed to fetch page {page} of collection: {e}")
                break

            releases = data.get("releases", [])
            if not releases:
                break

            all_releases.extend({"discogs_release_id": r["id"]} for r in releases)

            pagination = data.get("pagination", {})
            if page >= pagination.get("pages", 1):
                break

            page += 1

        logger.info(f"📀 Fetched {len(all_releases)} releases from Discogs collection.")
        return all_releases

    def get_oauth_identity(self, token: str, secret: str):
        """Make the OAuth identity call using OAuth 1.0"""
        try:
            oauth = OAuth1Session(
                client_key=settings.DISCOGS_CONSUMER_KEY,
                client_secret=settings.DISCOGS_SECRET_KEY,
                resource_owner_key=token,
                resource_owner_secret=secret,
            )

            url = f"{self.base_url}/oauth/identity"
            response = oauth.get(url)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"❌ Discogs OAuth identity call failed with status code {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Error during OAuth identity call: {e}")
            return None

    def get_full_release_details(self, release_id: int, token: str, secret: str) -> Optional[dict]:
        """Fetch full release details from Discogs and return the relevant data."""
        url = f"{self.base_url}/releases/{release_id}"

        oauth = OAuth1Session(
            client_key=settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_SECRET_KEY,
            resource_owner_key=token,
            resource_owner_secret=secret
        )

        try:
            response = oauth.get(url, headers={"User-Agent": "VinylScrobbler/1.0"})
            response.raise_for_status()

            # Get remaining calls from the header
            headers = response.headers
            remaining_calls = int(headers.get("x-discogs-ratelimit-remaining"))

            # Handle rate-limiting using remaining calls
            self._rate_limit(remaining_calls)

            release_data = response.json()

            images =  [{"uri": image["uri"], "uri150": image["uri150"]} for image in
                            release_data.get("images", [])]
            image = None
            image_thumbnail = None
            if images:
                if len(images) > 0:
                    image = images[0]["uri"]
                    image_thumbnail = images[0]["uri150"]
            tracks = []
            for track in release_data.get("tracklist", []):
                # Construct track data
                track_data = {
                    "track_number": track.get("position"),  # Track position
                    "title": track.get("title"),
                    "duration": track.get("duration"),
                    "extra_artists": [
                        {
                            "name": artist["name"],
                            "role": artist.get("role", ""),
                            "id": artist.get("id", "")
                        }
                        for artist in track.get("extraartists", [])
                    ],
                }
                tracks.append(track_data)
            return {
                "discogs_release_id": release_data["id"],
                "title": release_data.get("title"),
                "styles": ", ".join(release_data.get("styles", [])) if release_data.get("styles") else None,
                "country": release_data.get("country"),
                "artists": [{"discogs_artist_id": artist["id"], "name": artist["name"]} for artist in
                            release_data.get("artists", [])],
                "tracklist": tracks,
                "master_id": release_data.get("master_id"),
                "quality": release_data.get("data_quality"),
                "release_date": release_data.get("released"),
                "image_url": image,
                "thumbnail_url":image_thumbnail,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch full release details for {release_id}: {e}")
            return None

    def get_artist(self, artist_id: int, token, secret) -> Optional[dict]:
        """Fetch artist details from Discogs and return the relevant data."""
        url = f"{self.base_url}/artists/{artist_id}"
        headers = {
            "User-Agent": "VinylScrobbler/1.0"
        }

        oauth = OAuth1Session(
            client_key=settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_SECRET_KEY,
            resource_owner_key=token,
            resource_owner_secret=secret
        )

        try:
            response = oauth.get(url, headers={"User-Agent": "VinylScrobbler/1.0"})
            response.raise_for_status()
            data = response.json()

            return {
                "discogs_artist_id": data["id"],
                "name": data["name"],
                "namevariations": data.get("namevariations", []),
                "profile": data["profile"],
                "quality": data.get("data_quality"),
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch artist {artist_id}: {e}")
            return None


    def search(self, token, secret, type:str, artist:str = None, release_title:str = None, track: str= None) -> Optional[dict]:
        """Fetch artist details from Discogs and return the relevant data."""
        url = f"{self.base_url}/database/search?type={type}"
        headers = {
            "User-Agent": "VinylScrobbler/1.0"
        }
        if artist:
            url += f"&artist={artist}"
        if track:
            url += f"&track={track}"
        if release_title:
            url += f"&release_title={release_title}"

        oauth = OAuth1Session(
            client_key=settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_SECRET_KEY,
            resource_owner_key=token,
            resource_owner_secret=secret
        )

        try:
            response = oauth.get(url, headers={"User-Agent": "VinylScrobbler/1.0"})
            response.raise_for_status()
            data = response.json()

            if len(data.get("results", [])) > 0:
                return data.get("results")

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch data")
            return None

    def get_master(self, master_id: int, token, secret) -> Optional[dict]:
        """Fetch a master release (album-level abstraction) from Discogs."""
        url = f"{self.base_url}/masters/{master_id}"
        headers = {
            "User-Agent": "VinylScrobbler/1.0"
        }

        oauth = OAuth1Session(
            client_key=settings.DISCOGS_CONSUMER_KEY,
            client_secret=settings.DISCOGS_SECRET_KEY,
            resource_owner_key=token,
            resource_owner_secret=secret
        )

        try:
            response = oauth.get(url, headers={"User-Agent": "VinylScrobbler/1.0"})
            response.raise_for_status()

            # Get remaining calls from the header
            headers = response.headers
            remaining_calls = int(headers.get("x-discogs-ratelimit-remaining"))

            # Handle rate-limiting using remaining calls
            self._rate_limit(remaining_calls)

            data = response.json()
            return {
                "discogs_master_id": data.get("id"),
                "title": data.get("title"),
                "main_release": data.get("main_release"),
                "country": data.get("country"),
                "styles": data.get("styles", []),
                "year": data.get("year"),
                "artists": [{"discogs_artist_id": a["id"], "name": a["name"]} for a in data.get("artists", [])],
                "tracklist": [{"title": t["title"]} for t in data.get("tracklist", [])],
                "quality": data.get("data_quality"),
            }

        except requests.RequestException as e:
            logger.error(f"❌ Failed to fetch master {master_id}: {e}")
            return None
