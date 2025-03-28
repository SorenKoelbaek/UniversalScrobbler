import asyncio
import ssl
import base64
import os
import aiohttp
import struct
import uuid
import time
from config import settings
from google.protobuf import text_format
from scripts.protos import connect_pb2, spirc_pb2, player_pb2
from services.spotify_service import SpotifyService
from sqlmodel.ext.asyncio.session import AsyncSession
from dependencies.database import get_async_engine
from sqlmodel import select
from models.sqlmodels import User
import logging
WS_URL = "wss://dealer.spotify.com/"  # Use the correct endpoint
logger = logging.getLogger(__name__)


spotify_service = SpotifyService()

def build_subscribe_frame():
    uri = "hm://connect-state/v1/devices"
    uri_bytes = uri.encode()
    header = struct.pack(">H", len(uri_bytes)) + uri_bytes
    return header + b"\x00\x00" + struct.pack(">H", 1) + struct.pack(">H", 0)

def build_put_frame(uri: str, payload: bytes):
    uri_bytes = uri.encode()
    header = struct.pack(">H", len(uri_bytes)) + uri_bytes
    flags = b"\x00\x03"  # PUT flag
    count = struct.pack(">H", 1)
    body = struct.pack(">H", len(payload)) + payload
    return header + flags + count + body

def build_put_state(device_id: str):
    req = connect_pb2.PutStateRequest()
    req.device.device_info.device_id = device_id
    req.device.device_info.device_type = connect_pb2.BUILT_IN_SPEAKER
    req.device.device_info.name = "UniversalScrobbler"
    req.device.device_info.brand = "Python"
    req.device.device_info.model = "DIY"
    req.device.device_info.spirc_version = "3.2.6"
    req.device.private_device_info.platform = "windows"
    req.device.transfer_data = b"\x00"
    caps = req.device.device_info.capabilities
    caps.supports_logout = True
    caps.supports_playlist_v2 = True
    caps.supports_transfer_command = True
    caps.supports_set_backend_metadata = True
    caps.supports_command_request = True
    caps.supports_set_options_command = True
    caps.supported_types.append("audio/local")
    caps.can_be_player = True
    caps.is_controllable = True
    ps = req.device.player_state
    now = int(time.time() * 1000)
    ps.timestamp = now
    ps.position_as_of_timestamp = now
    ps.duration = 0
    ps.position = 0
    ps.is_paused = True
    ps.is_playing = False
    ps.is_buffering = False
    ps.is_system_initiated = False
    ps.session_id = str(uuid.uuid4())
    ps.context_uri = "spotify:playlist:fake"
    logger.info("PUT State - PlayerState fields:")
    for field, value in ps.ListFields():
        logger.info(f" - {field.name}: {value}")
    return req

def build_spirc_hello(device_id, connection_id):
    frame = spirc_pb2.Frame()
    frame.version = 1
    frame.ident = device_id
    frame.protocol_version = "1.0"
    frame.seq_nr = 1
    frame.typ = spirc_pb2.kMessageTypeHello

    ds = spirc_pb2.DeviceState()
    ds.sw_version = "3.2.6"
    ds.is_active = True
    ds.can_play = True
    ds.volume = 100
    ds.name = "UniversalScrobbler"
    ds.error_code = 0
    ds.became_active_at = int(time.time() * 1000)
    ds.error_message = ""
    cap1 = spirc_pb2.Capability()
    cap1.typ = spirc_pb2.kSupportsPlaylistV2
    cap1.intValue.append(1)
    ds.capabilities.append(cap1)
    try:
        cap2 = spirc_pb2.Capability()
        cap2.typ = spirc_pb2.kSupportsLogout
        cap2.intValue.append(1)
        ds.capabilities.append(cap2)
    except AttributeError:
        pass
    try:
        cap3 = spirc_pb2.Capability()
        cap3.typ = spirc_pb2.kSupportsRename
        cap3.intValue.append(1)
        ds.capabilities.append(cap3)
    except AttributeError:
        pass

    frame.device_state.CopyFrom(ds)
    return frame

def build_spirc_probe_response(device_id, connection_id, seq_nr):
    """
    Build a SPIRC Probe response message. This mirrors the probe handling in spotcontrol.
    We simply construct a Frame with typ = kMessageTypeProbe and the same seq_nr.
    """
    frame = spirc_pb2.Frame()
    frame.version = 1
    frame.ident = device_id
    frame.protocol_version = "1.0"
    frame.seq_nr = seq_nr
    frame.typ = spirc_pb2.kMessageTypeProbe  # Using Probe type as response.
    # For probe responses, DeviceState can be empty.
    return frame

async def send_spirc_hello(ws, device_id, connection_id):
    hello_msg = build_spirc_hello(device_id, connection_id)
    serialized = hello_msg.SerializeToString()
    logger.info("Sending SPIRC Hello:")
    logger.info(text_format.MessageToString(hello_msg))
    await ws.send_bytes(serialized)

async def send_put_state(ws, device_id):
    put_state = build_put_state(device_id)
    payload = put_state.SerializeToString()
    put_uri = f"hm://connect-state/v1/devices/{device_id}"
    frame = build_put_frame(put_uri, payload)
    logger.info("Sending PUT state registration for device %s", device_id)
    await ws.send_bytes(frame)

async def send_subscribe(ws):
    subscribe_frame = build_subscribe_frame()
    logger.info("Sending subscription frame")
    await ws.send_bytes(subscribe_frame)

async def send_probe_response(ws, device_id, connection_id, seq_nr):
    response = build_spirc_probe_response(device_id, connection_id, seq_nr)
    serialized = response.SerializeToString()
    logger.info("Sending SPIRC Probe response:")
    logger.info(text_format.MessageToString(response))
    await ws.send_bytes(serialized)

async def heartbeat(ws, device_id, connection_id):
    """Send periodic SPIRC probe frames as heartbeats."""
    seq_nr = 2  # Starting sequence number for heartbeats
    while True:
        try:
            response = build_spirc_probe_response(device_id, connection_id, seq_nr)
            serialized = response.SerializeToString()
            await ws.send_bytes(serialized)
            logger.info("Sent SPIRC probe heartbeat, seq_nr: %s", seq_nr)
            seq_nr += 1
        except Exception as e:
            logger.error("Heartbeat error: %s", e)
            break
        await asyncio.sleep(30)

async def listen_to_spotify(HEADERS: dict, connection_id: str):
    logger.info("Connecting via aiohttp...")
    ssl_context = ssl._create_unverified_context()
    device_id = str(uuid.uuid4())
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            WS_URL,
            headers=HEADERS,
            ssl=ssl_context,
            max_msg_size=0
        ) as ws:
            logger.info("Connected.")

            # Handshake sequence:
            await send_subscribe(ws)
            await send_put_state(ws, device_id)
            await send_spirc_hello(ws, device_id, connection_id)
            asyncio.create_task(heartbeat(ws, device_id, connection_id))

            while True:
                msg = await ws.receive()
                logger.info("Received message of type: %s", msg.type)
                if msg.type == aiohttp.WSMsgType.BINARY:
                    logger.info("Binary message (%s bytes)", len(msg.data))
                    logger.info("Raw (first 64 bytes): %s", msg.data[:64].hex(" "))
                    try:
                        frame = spirc_pb2.Frame()
                        frame.ParseFromString(msg.data)
                        logger.info("Parsed SPIRC Frame:")
                        logger.info(text_format.MessageToString(frame))
                        # If it's a probe message, reply with a probe response.
                        if frame.typ == spirc_pb2.kMessageTypeProbe:
                            logger.info("Received probe; sending response")
                            await send_probe_response(ws, device_id, connection_id, frame.seq_nr)
                    except Exception as e:
                        logger.error("Failed to parse SPIRC frame: %s", e)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    logger.info("Text Message: %s", msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket closed by server.")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket error: %s", msg)
                    break


async def do_the_thing():
    engine = get_async_engine()
    async with AsyncSession(engine) as session:
        result = await session.exec(select(User))
        users = result.all()

        logger.info(f"Found {len(users)} users")
        if not users:
            logger.info("No users found in the database.")
            return

        for user in users:
            access_token = await spotify_service.get_token_for_user(user.user_uuid, session)

            spotify_connection_id = base64.b64encode(os.urandom(96)).decode()
            header = {
                "Authorization": f"Bearer {access_token}",
                "Spotify-Connection-Id": spotify_connection_id,
            }
            await listen_to_spotify(header, spotify_connection_id)


if __name__ == "__main__":
    asyncio.run(do_the_thing())
