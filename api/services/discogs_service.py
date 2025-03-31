from typing import List, Optional, Set
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import HTTPException, BackgroundTasks
from models.sqlmodels import DiscogsToken, DiscogsOAuthTemp, TrackVersionAlbumReleaseBridge, TrackAlbumBridge, \
    TrackVersion, TrackArtistBridge
from models.sqlmodels import Album, AlbumArtistBridge, Artist, Track, Collection, CollectionAlbumBridge, AlbumRelease, \
    AlbumReleaseArtistBridge, CollectionAlbumReleaseBridge
from sqlmodel import select, delete
from sqlalchemy.orm import selectinload
from models.appmodels import CollectionRead, AlbumRead, ArtistRead, TrackRead
from dependencies.discogs_api import DiscogsAPI
from services.collection_service import CollectionService
import requests
import uuid
from datetime import datetime
import time
from uuid import UUID

from config import settings
import logging
logger = logging.getLogger(__name__)


def parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        date_str = str(date_str)
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y")
        except ValueError:
            return None


DISCOGS_REQUEST_TOKEN_URL = "https://api.discogs.com/oauth/request_token"
DISCOGS_AUTHORIZE_URL = "https://www.discogs.com/oauth/authorize"
DISCOGS_ACCESS_TOKEN_URL = "https://api.discogs.com/oauth/access_token"


class DiscogsService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.oauth = {}  # add Discogs Ouath flow stuff here
            cls._instance.api = DiscogsAPI()
        return cls._instance

    async def authorize_user(self, oauth_token: str, oauth_verifier: str, user_uuid: str, db: AsyncSession):
        # Fetch the temporary OAuth data from DiscogsOAuthTemp table
        result = await db.execute(
            select(DiscogsOAuthTemp).where(DiscogsOAuthTemp.oauth_token == oauth_token)
        )
        temp = result.scalars().first()

        if not temp or temp.user_uuid != user_uuid:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth token")

        token_secret = temp.oauth_token_secret
        oauth_nonce = uuid.uuid4().hex
        oauth_timestamp = str(int(time.time()))

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": (
                f'OAuth oauth_consumer_key="{settings.DISCOGS_CONSUMER_KEY}", '
                f'oauth_nonce="{oauth_nonce}", '
                f'oauth_token="{oauth_token}", '
                f'oauth_signature="{settings.DISCOGS_SECRET_KEY}&{token_secret}", '  # Fixed this line
                f'oauth_signature_method="PLAINTEXT", '
                f'oauth_timestamp="{oauth_timestamp}", '
                f'oauth_verifier="{oauth_verifier}"'
            ),
            "User-Agent": "VinylScrobbler/1.0",
        }

        try:
            # Sending request to Discogs API to exchange the OAuth token for an access token
            response = requests.post(DISCOGS_ACCESS_TOKEN_URL, headers=headers)

            if response.status_code != 200:
                logger.error(f"Discogs response error: {response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange token")

            content = dict(item.split("=") for item in response.text.split("&"))
            access_token = content["oauth_token"]
            access_token_secret = content["oauth_token_secret"]

            # Clean up the temporary OAuth data from DiscogsOAuthTemp table
            try:
                await db.delete(temp)
                await db.commit()
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean up DiscogsOAuthTemp: {e}")

            return await self.add_token_for_user(access_token, access_token_secret, user_uuid,
                                                 db)  # You can return the access token here or proceed with the desired flow

        except Exception as e:
            logger.error(f"Error during the authorization process: {e}")
            raise HTTPException(status_code=500, detail="An error occurred during the authorization process")

    async def add_token_for_user(self, access_token: str, access_token_secret: str, user_uuid: str, db: AsyncSession):
        result = await db.execute(select(DiscogsToken).where(DiscogsToken.user_uuid == user_uuid))
        token = result.scalars().first()

        if not token:
            token = DiscogsToken(user_uuid=user_uuid, access_token=access_token,
                                 access_token_secret=access_token_secret)
            db.add(token)
            await db.commit()
            await db.refresh(token)

        return token.access_token

    async def get_redirect_url(self, user_uuid: str, db: AsyncSession) -> str:
        oauth_nonce = str(uuid.uuid4().hex)
        oauth_timestamp = str(int(time.time()))

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": (
                f'OAuth oauth_consumer_key="{settings.DISCOGS_CONSUMER_KEY}", '
                f'oauth_nonce="{oauth_nonce}", '
                f'oauth_signature="{settings.DISCOGS_SECRET_KEY}&", '
                f'oauth_signature_method="PLAINTEXT", '
                f'oauth_timestamp="{oauth_timestamp}", '
                f'oauth_callback="{settings.DISCOGS_CALLBACK_URL}"'
            ),
            "User-Agent": "VinylScrobbler/1.0",
        }

        response = requests.get(DISCOGS_REQUEST_TOKEN_URL, headers=headers)

        if response.status_code != 200:
            raise Exception(f"Failed to get request token: {response.text}")

        content = dict(item.split("=") for item in response.text.split("&"))
        oauth_token = content["oauth_token"]
        oauth_token_secret = content["oauth_token_secret"]

        # Store the secret temporarily
        temp = DiscogsOAuthTemp(
            oauth_token=oauth_token,
            oauth_token_secret=oauth_token_secret,
            user_uuid=user_uuid  # passed from the current session/user
        )
        db.add(temp)
        await db.commit()

        # Redirect user to Discogs for authorization
        return f"{DISCOGS_AUTHORIZE_URL}?oauth_token={oauth_token}"

    async def get_token_for_user(self, user_uuid: str, db: AsyncSession):
        result = await db.execute(select(DiscogsToken).where(DiscogsToken.user_uuid == user_uuid))
        token = result.scalars().first()

        if not token:
            raise HTTPException(status_code=404, detail="Discogs token not found for user.")

        return token

    ## these are new
    async def get_or_create_artist(self, artist_data: dict, token: str, secret: str, db: AsyncSession) -> Artist:
        discogs_id = artist_data.get("discogs_artist_id")
        result = await db.execute(select(Artist).where(Artist.discogs_artist_id == discogs_id))
        artist = result.scalars().first()
        if artist:
            return artist
        artist_details = self.api.get_artist(discogs_id, token, secret)
        artist = Artist(
            discogs_artist_id=discogs_id,
            name=artist_details.get("name"),
            name_variations=", ".join(artist_details.get("namevariations", [])) if artist_details.get(
                "namevariations") else None,
            profile=artist_details.get("profile"),
            quality=artist_details.get("quality"),
        )
        db.add(artist)
        await db.flush()
        return artist

    async def get_or_create_collection(self, user_uuid: str, collection_name: str, db: AsyncSession):
        """Helper function to check if a user exists and create it if not."""
        collection_service=CollectionService(db)
        result = await db.execute(select(Collection).where(Collection.user_uuid == user_uuid))
        collection = result.scalars().first()
        if not collection:
            collection = Collection(user_uuid=user_uuid, collection_name=collection_name)
            db.add(collection)
            await db.flush()

        return await collection_service.get_collection_simple(collection.collection_uuid)

    async def get_or_create_track(self, track_data, album_release, token:str, secret:str, db: AsyncSession):
        # 1. Ensure track exists in the database based on both track_name and artist
        track_name = track_data.get("title")
        extra_artists = track_data.get("extra_artists", [])
        # Collect artist UUIDs from the main artists on the album_release and extra artists
        artist_uuids = [artist.artist_uuid for artist in album_release.artists]
        logger.info("checking if bridge already exists")
        # Query the database to check if the track already exists for this artist
        result = await db.execute(
            select(Track)
            .join(TrackArtistBridge)
            .where(
                Track.name == track_name,
                TrackArtistBridge.artist_uuid.in_(artist_uuids)  # Corrected to use .in_() for "IN" operator
            )
        )
        track = result.scalar_one_or_none()
        if track:
            return track
        else:
            logger.info("Track doesn't exists")
            track = Track(
                name=track_name,
            )
            db.add(track)
            await db.flush()
            logger.info("Track created")
            # Link the track to the artists (via TrackArtistBridge)
            logger.info("linking track")
            for artist_uuid in artist_uuids:
                track_artist_link = TrackArtistBridge(track_uuid=track.track_uuid, artist_uuid=artist_uuid)
                db.add(track_artist_link)
                await db.flush()

        return track

    async def get_or_create_track_version(self, track, track_data, album_release, db: AsyncSession):
        logger.info("checking if track version exists")
        # Check if the track version already exists
        result = await db.execute(
            select(TrackVersion)
            .join(TrackVersionAlbumReleaseBridge)
            .where(
                TrackVersion.track_uuid == track.track_uuid,
                TrackVersion.duration == track_data.get("duration"),
                TrackVersionAlbumReleaseBridge.album_release_uuid == album_release.album_release_uuid
            )
        )
        trackversion = result.scalar_one_or_none()
        if trackversion:
            return trackversion
        else:
            logger.info("adding track version")
            # Create a new track version if it doesn't exist
            track_version = TrackVersion(
                track_uuid=track.track_uuid,
                duration=track_data.get("duration"),
                quality=track_data.get("quality")
            )
            db.add(track_version)
            await db.flush()

            # 3. Link track version to album release
            logger.info("linking track version to album release")
            track_version_album_release_link = TrackVersionAlbumReleaseBridge(
                track_version_uuid=track_version.track_version_uuid,
                album_release_uuid=album_release.album_release_uuid,
                track_number=track_data.get("track_number")  # Optional
            )
            db.add(track_version_album_release_link)
            await db.flush()
        return track_version

    async def link_artists_to_release(self, release_artists: List[dict], album_release: AlbumRelease, album: Album,
                                      token: str, secret: str,
                                      db: AsyncSession):
        for artist_data in release_artists:
            artist = await self.get_or_create_artist(artist_data, token, secret, db)

            result = await db.execute(
                select(AlbumReleaseArtistBridge).where(
                    AlbumReleaseArtistBridge.album_release_uuid == album_release.album_release_uuid,
                    AlbumReleaseArtistBridge.artist_uuid == artist.artist_uuid
                )
            )
            existing_link = result.scalars().first()
            if not existing_link:
                db.add(AlbumReleaseArtistBridge(
                    artist_uuid=artist.artist_uuid,
                    album_release_uuid=album_release.album_release_uuid
                ))

        await db.flush()

    async def create_master_album(self, master_data: dict, token: str, secret: str, db: AsyncSession):
        try:
            # Check if the album already exists (without loading artists)
            result = await db.execute(
                select(Album).where(Album.discogs_master_id == master_data.get("discogs_master_id"))
            )
            album = result.scalar_one_or_none()

            # If the album exists, return it with the artists eagerly loaded
            if album:
                # Eagerly load the artists for the existing album
                await db.execute(
                    select(Album).where(Album.album_uuid == album.album_uuid).options(selectinload(Album.artists)))
                return album

            # Create a new album if it doesn't exist
            new_album = Album(
                discogs_master_id=master_data.get("discogs_master_id"),
                title=master_data.get("title"),
                country=master_data.get("country"),
                styles=", ".join(master_data.get("styles", [])) if master_data.get("styles") else None,
                release_date=parse_date(master_data.get("year")),
                discogs_main_release_id=master_data.get("main_release"),
                quality=master_data.get("quality"),
            )

            # Add the new album to the session
            db.add(new_album)
            await db.flush()  # Flush to the database to get the UUID assigned

            # Eagerly load the artists after the flush
            await db.execute(
                select(Album).where(Album.album_uuid == new_album.album_uuid).options(selectinload(Album.artists)))

            # The artists will now be available
            await self.link_artists_to_album(new_album, master_data.get("artists", []), token, secret, db)

            return new_album
        except Exception as e:
            logger.error(f"Failed to create or fetch album: {e}")
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    async def create_master_album_from_release(self, release_data, token: str, secret: str, db: AsyncSession):
        album = Album(
            discogs_master_id=None,
            title=release_data.get("title"),
            country=release_data.get("country"),
            release_date=parse_date(release_data.get("released")),
            discogs_main_release_id=release_data.get("discogs_release_id"),
            quality=release_data.get("quality"),
        )
        db.add(album)
        await db.flush()

        result = await db.execute(
            select(Album).where(Album.album_uuid == album.album_uuid).options(selectinload(Album.artists))
        )
        album = result.scalar_one()
        await self.link_artists_to_album(album, release_data.get("artists", []), token, secret, db)

        return album

    async def get_or_create_album_from_master(
            self, release_data: dict, token: str, secret: str, db: AsyncSession
    ) -> Album:
        master_id = release_data.get("master_id")

        if master_id:
            # If there's a master_id, try to find the album from the master ID
            result = await db.execute(
                select(Album).where(Album.discogs_master_id == master_id).options(selectinload(Album.artists))
            )
            album = result.scalar_one_or_none()

            if album:
                return album  # If found, return it

            # If not found, fetch the master data from the API
            master_data = self.api.get_master(master_id, token, secret)
            if not master_data:
                raise ValueError(f"Master data not found for master_id: {master_id}")

            # Create the album from the master data if available
            album = await self.create_master_album(master_data, token, secret, db)

        else:
            # If no master_id, create the album directly from the release data
            logger.warning(f"No master_id found in release data: {release_data['discogs_release_id']}")
            album = await self.create_master_album_from_release(release_data, token, secret, db)

        return album

    async def link_artists_to_album(
            self, album: Album, discogs_artists: List[dict], token: str, secret: str, db: AsyncSession
    ):
        for artist_data in discogs_artists:
            discogs_id = artist_data.get("discogs_artist_id")
            if not discogs_id:
                continue  # Skip invalid entries

            result = await db.execute(select(Artist).where(Artist.discogs_artist_id == discogs_id))
            artist = result.scalars().first()

            if not artist:
                # Fetch full artist info if not in DB
                artist_details = self.api.get_artist(discogs_id, token, secret)
                artist = Artist(
                    discogs_artist_id=discogs_id,
                    name=artist_details.get("name"),
                    name_variations=", ".join(artist_details.get("namevariations", [])) if artist_details.get(
                        "namevariations") else None,
                    profile=artist_details.get("profile"),
                )
                db.add(artist)
                await db.flush()

            # Link artist to album only if not already linked
            if artist not in album.artists:
                album.artists.append(artist)

        await db.flush()

    async def add_album_with_release_details(self, release_data: dict, token: str, secret: str, db: AsyncSession):
        if not release_data.get("master_id"):
            logger.warning(f"can't find master on release: {release_data['discogs_release_id']}")

        # Get or create the album from the master (or release)
        album = await self.get_or_create_album_from_master(release_data, token, secret, db)

        try:
            # Check if it's the main release for the album
            is_main = release_data["discogs_release_id"] == album.discogs_main_release_id

            # Create the album release object
            album_release = AlbumRelease(
                title=release_data["title"],
                discogs_release_id=release_data["discogs_release_id"],
                country=release_data.get("country"),
                release_date=parse_date(release_data.get("release_date")),
                album=album,
                is_main_release=is_main,
                quality=release_data.get("quality"),
                image_url=release_data.get("image_url"),
                image_thumbnail_url=release_data.get("thumbnail_url"),
            )
            db.add(album_release)
            await db.flush()

            # Add artists to the album release (but only if different from album level)
            await self.link_artists_to_release(release_data["artists"], album_release, album, token, secret, db)

            # Add tracks
            for track_data in release_data.get("tracklist", []):
                await self.add_track_to_db(
                    track_data,  # Pass the track data
                    album,  # The album to associate with
                    album_release,  # The album release to associate with
                    token,
                    secret,
                    db,  # The database session
                )


        except Exception as e:
            logger.error(f"Failed to create album release {release_data['title']} by {release_data['artists']}: {e}")
        return album, album_release

    async def add_track_to_db(self,
                              track_data: dict,
                              album: Album,
                              album_release: AlbumRelease,
                              token:str,
                              secret: str,
                              db: AsyncSession
                              ):

        # No need to query for album and album_release again if they're passed into the function
        if not album or not album_release:
            raise HTTPException(status_code=404, detail="Album or AlbumRelease not found")

        album_result = await db.execute(
            select(Album).where(Album.album_uuid == album.album_uuid).options(selectinload(Album.artists)))
        album = album_result.scalar_one_or_none()


        release_result = await db.execute(
            select(AlbumRelease).where(AlbumRelease.album_release_uuid == album_release.album_release_uuid).options(
                selectinload(AlbumRelease.artists)))
        album_release = release_result.scalar_one_or_none()

        # Create or get the track
        try:
            track = await self.get_or_create_track(track_data, album_release,token,secret, db)
        except Exception as e:
            logger.debug(f"couldn't create track {track_data['title']} by {track_data['artists']}: {e}")

        # Create or get the track version
        try:
            track_version = await self.get_or_create_track_version(track, track_data, album_release, db)
        except Exception as e:
            logger.debug(f"couldn't create track-version {track_data['title']} by {track_data['artists']}: {e}")

        try:
            # Check if the track is already linked to the album
            linked_result = await db.execute(
                select(TrackAlbumBridge).where(
                    TrackAlbumBridge.track_uuid == track.track_uuid,
                    TrackAlbumBridge.album_uuid == album.album_uuid
                )
            )
            islinked = linked_result.scalar_one_or_none()

            # If not linked, add the track to the album
            if not islinked:
                track_album_link = TrackAlbumBridge(track_uuid=track.track_uuid, album_uuid=album.album_uuid)
                db.add(track_album_link)
                await db.flush()

            return track
        except Exception as e:
            logger.error("couldn't link track to album")

    async def get_or_create_album_from_release(self, release_id: int, token: str, secret: str, db: AsyncSession):
        result = await db.execute(select(AlbumRelease).where(AlbumRelease.discogs_release_id == release_id))
        album_release = result.scalars().first()
        if album_release:
            logger.info(f"found existing album release: {release_id}")
            return album_release.album, album_release

        logger.info(f"Getting album and release information: {release_id}")
        release_data = self.api.get_full_release_details(release_id, token, secret)
        album, album_release = await self.add_album_with_release_details(release_data, token, secret, db)

        return album, album_release


    async def get_album_from_discogs(self, user_uuid: str, db: AsyncSession, artist:str=None, album:str=None, track:str=None):
        auth = await self.get_token_for_user(user_uuid, db)
        token = auth.access_token
        secret = auth.access_token_secret

        results = self.api.search(token, secret,type="master", artist=artist, release_title=album, track=track)
        try:
            largest_community = max(
                results,
                key=lambda x: x["community"]["want"] + x["community"]["have"]
            )
            master_data = self.api.get_master(largest_community["id"], token, secret)
            album = await self.create_master_album(master_data, token, secret, db)

            result = await db.execute(select(Album)
            .where(
                Track.albums.any(Album.album_uuid == album.album_uuid)
            )
            .options(
            selectinload(Album.artists),
                    selectinload(Album.tracks)
                )  # Ensure related fields are loaded
            )
            found_album = result.scalars().first()
            return Album.model_validate(found_album)  # Use model_validate instead of parse_obj
        except Exception as e:
            logger.error(f"Failed to get discogs results: {e}")

    async def get_track_from_discogs(self, user_uuid: str, db: AsyncSession, artist:str=None, album:str=None, track:str=None):
        auth = await self.get_token_for_user(user_uuid, db)
        token = auth.access_token
        secret = auth.access_token_secret

        results = self.api.search(token, secret,type="master", artist=artist, release_title=album, track=track)
        logger.info(f"found discogs results: {results}")
        try:
            largest_community = max(
                results,
                key=lambda x: x["community"]["want"] + x["community"]["have"]
            )
            master_data = self.api.get_master(largest_community["id"], token, secret)
            #create album
            album = await self.create_master_album(master_data, token, secret, db)
            release_data = self.api.get_full_release_details(master_data.get("main_release"), token, secret)
            try:
                album_release = AlbumRelease(
                    title=release_data["title"],
                    discogs_release_id=release_data["discogs_release_id"],
                    country=release_data.get("country"),
                    release_date=parse_date(release_data.get("release_date")),
                    album=album,
                    is_main_release=True,
                    quality=release_data.get("quality"),
                    image_url=release_data.get("image_url"),
                    image_thumbnail_url=release_data.get("thumbnail_url"),
                )
                db.add(album_release)
                await db.flush()

                # Add artists to the album release (but only if different from album level)
                await self.link_artists_to_release(release_data["artists"], album_release, album, token, secret, db)

                # Add tracks
                for track_data in release_data.get("tracklist", []):
                    await self.add_track_to_db(
                        track_data,  # Pass the track data
                        album,  # The album to associate with
                        album_release,  # The album release to associate with¨
                        token,
                        secret,
                        db,  # The database session
                    )
            except Exception as e:
                logger.error(f"Failed to get discogs results: {e}")

            # refetch result!
            result = await db.execute(select(Track)
            .where(
                Track.name.ilike(f"%{track}%"),
                Track.albums.any(Album.album_uuid == album.album_uuid)
            ).options(
                selectinload(Track.albums).selectinload(Album.artists)))

            found_track = result.scalar_one_or_none()
            logger.info(f"found_track {found_track}")

            return TrackRead.model_validate(found_track)  # Use model_validate instead of parse_obj
        except Exception as e:
            logger.error(f"Failed to get discogs results: {e}")

    async def update_user_collection(self, user_uuid: str, db: AsyncSession):
        auth = await self.get_token_for_user(user_uuid, db)
        token = auth.access_token
        secret = auth.access_token_secret

        collection = await self.get_or_create_collection(user_uuid, "Discogs main collection", db)
        releases = self.api.get_collection(token, secret)

        discogs_release_ids = {r["discogs_release_id"] for r in releases}
        existing_release_ids = {r.discogs_release_id for r in collection.album_releases}

        logger.info(f"found {len(discogs_release_ids)} releases in collection and {len(discogs_release_ids)} discogs releases ")

        # delete releses from collection that are not in discogs collection
        for existing_release in [existing_release for existing_release in collection.album_releases if existing_release.discogs_release_id not in discogs_release_ids]:
            logger.info(f"deleting existing release: {existing_release}")
            await db.execute(
                delete(CollectionAlbumReleaseBridge).where(
                    CollectionAlbumReleaseBridge.album_release_uuid == existing_release.album_release_uuid,
                    CollectionAlbumReleaseBridge.collection_uuid == collection.collection_uuid,
                )
            )
        # insert new releases!
        for release in [release for release in releases if release["discogs_release_id"] not in existing_release_ids]:
            release_id = release["discogs_release_id"]
            logger.info(f"Retriving and adding release: {release_id}")
            try:
                album, album_release = await self.get_or_create_album_from_release(release_id, token, secret, db)
                await self.link_release_to_collection(album_release.album_release_uuid, collection.collection_uuid, db)
                await db.commit()
            except Exception as e:
                # Log the error, but continue processing the next releases
                logger.error(f"❌ Error processing release {release_id}: {e}")
                continue  # Continue with the next release

        return True

    async def link_release_to_collection(
            self,
            album_release_uuid: UUID,
            collection_uuid: UUID,
            db: AsyncSession,
    ):
        # Get the release and its parent album
        result = await db.execute(
            select(AlbumRelease).where(AlbumRelease.album_release_uuid == album_release_uuid)
        )
        album_release = result.scalars().first()
        if not album_release:
            raise ValueError("AlbumRelease not found")

        album = album_release.album
        if not album:
            raise ValueError("AlbumRelease has no parent Album")

        # Link album (master) to collection
        result = await db.execute(
            select(CollectionAlbumBridge).where(
                CollectionAlbumBridge.album_uuid == album.album_uuid,
                CollectionAlbumBridge.collection_uuid == collection_uuid,
            )
        )
        album_bridge = result.scalars().first()
        if not album_bridge:
            album_bridge = CollectionAlbumBridge(
                album_uuid=album.album_uuid,
                collection_uuid=collection_uuid,
            )
            db.add(album_bridge)

        # Link specific release to collection
        result = await db.execute(
            select(CollectionAlbumReleaseBridge).where(
                CollectionAlbumReleaseBridge.album_release_uuid == album_release_uuid,
                CollectionAlbumReleaseBridge.collection_uuid == collection_uuid,
            )
        )
        release_bridge = result.scalars().first()
        if not release_bridge:
            release_bridge = CollectionAlbumReleaseBridge(
                album_release_uuid=album_release_uuid,
                collection_uuid=collection_uuid,
            )
            db.add(release_bridge)

        await db.flush()

    async def get_collection(self, user_uuid: str, db: AsyncSession) -> CollectionRead:
        result = await db.execute(
            select(Collection)
            .where(Collection.user_uuid == user_uuid)
            .options(
                selectinload(Collection.albums)
                .selectinload(Album.artists),
                selectinload(Collection.albums)
                .selectinload(Album.tracks)
            )
        )
        collection = result.scalars().first()

        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found.")

        # Convert to appmodels
        album_models = []
        for album in collection.albums:
            artist_models = [
                ArtistRead(
                    artist_uuid=a.artist_uuid,
                    name=a.name,
                    discogs_artist_id=a.discogs_artist_id,
                    name_variations=a.name_variations,
                    profile=a.profile,
                )
                for a in album.artists
            ]
            track_models = [
                TrackRead(track_uuid=t.track_uuid, name=t.name)
                for t in album.tracks
            ]

            album_models.append(
                AlbumRead(
                    album_uuid=album.album_uuid,
                    title=album.title,
                    discogs_release_id=album.discogs_release_id,
                    styles=album.styles,
                    country=album.country,
                    artists=artist_models,
                    tracks=track_models,
                )
            )

        return CollectionRead(
            collection_uuid=collection.collection_uuid,
            collection_name=collection.collection_name,
            albums=album_models
        )

    async def get_identity(self, user_uuid: str, db: AsyncSession):
        auth = await self.get_token_for_user(user_uuid, db)
        token = auth.access_token
        secret = auth.access_token_secret
        return self.api.get_oauth_identity(token, secret)
