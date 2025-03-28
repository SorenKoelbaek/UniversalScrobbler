import asyncio
import os
import socket
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies.database import get_async_engine
from services.spotify_service import SpotifyService
from google.protobuf import text_format
from scripts.protos import keyexchange_pb2
import hmac
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
from scripts.spotify_shannon import SpotifyShannon
from scripts.protos import mercury_pb2

logger = logging.getLogger(__name__)
spotify_service = SpotifyService()

# --- DH parameters ---
DH_P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF", 16)
DH_G = 2

SERVER_KEY = bytes([
    0xac, 0xe0, 0x46, 0x0b, 0xff, 0xc2, 0x30, 0xaf, 0xf4, 0x6b, 0xfe, 0xc3, 0xbf, 0xbf, 0x86, 0x3d,
    0xa1, 0x91, 0xc6, 0xcc, 0x33, 0x6c, 0x93, 0xa1, 0x4f, 0xb3, 0xb0, 0x16, 0x12, 0xac, 0xac, 0x6a,
    0xf1, 0x80, 0xe7, 0xf6, 0x14, 0xd9, 0x42, 0x9d, 0xbe, 0x2e, 0x34, 0x66, 0x43, 0xe3, 0x62, 0xd2,
    0x32, 0x7a, 0x1a, 0x0d, 0x92, 0x3b, 0xae, 0xdd, 0x14, 0x02, 0xb1, 0x81, 0x55, 0x05, 0x61, 0x04,
    0xd5, 0x2c, 0x96, 0xa4, 0x4c, 0x1e, 0xcc, 0x02, 0x4a, 0xd4, 0xb2, 0x0c, 0x00, 0x1f, 0x17, 0xed,
    0xc2, 0x2f, 0xc4, 0x35, 0x21, 0xc8, 0xf0, 0xcb, 0xae, 0xd2, 0xad, 0xd7, 0x2b, 0x0f, 0x9d, 0xb3,
    0xc5, 0x32, 0x1a, 0x2a, 0xfe, 0x59, 0xf3, 0x5a, 0x0d, 0xac, 0x68, 0xf1, 0xfa, 0x62, 0x1e, 0xfb,
    0x2c, 0x8d, 0x0c, 0xb7, 0x39, 0x2d, 0x92, 0x47, 0xe3, 0xd7, 0x35, 0x1a, 0x6d, 0xbd, 0x24, 0xc2,
    0xae, 0x25, 0x5b, 0x88, 0xff, 0xab, 0x73, 0x29, 0x8a, 0x0b, 0xcc, 0xcd, 0x0c, 0x58, 0x67, 0x31,
    0x89, 0xe8, 0xbd, 0x34, 0x80, 0x78, 0x4a, 0x5f, 0xc9, 0x6b, 0x89, 0x9d, 0x95, 0x6b, 0xfc, 0x86,
    0xd7, 0x4f, 0x33, 0xa6, 0x78, 0x17, 0x96, 0xc9, 0xc3, 0x2d, 0x0d, 0x32, 0xa5, 0xab, 0xcd, 0x05,
    0x27, 0xe2, 0xf7, 0x10, 0xa3, 0x96, 0x13, 0xc4, 0x2f, 0x99, 0xc0, 0x27, 0xbf, 0xed, 0x04, 0x9c,
    0x3c, 0x27, 0x58, 0x04, 0xb6, 0xb2, 0x19, 0xf9, 0xc1, 0x2f, 0x02, 0xe9, 0x48, 0x63, 0xec, 0xa1,
    0xb6, 0x42, 0xa0, 0x9d, 0x48, 0x25, 0xf8, 0xb3, 0x9d, 0xd0, 0xe8, 0x6a, 0xf9, 0x48, 0x4d, 0xa1,
    0xc2, 0xba, 0x86, 0x30, 0x42, 0xea, 0x9d, 0xb3, 0x08, 0x6c, 0x19, 0x0e, 0x48, 0xb3, 0x9d, 0x66,
    0xeb, 0x00, 0x06, 0xa2, 0x5a, 0xee, 0xa1, 0x1b, 0x13, 0x87, 0x3c, 0xd7, 0x19, 0xe6, 0x55, 0xbd,
])


def derive_keys(shared_key: bytes, client_hello: bytes, ap_response: bytes):
    combined = client_hello + ap_response
    data = b''

    for i in range(1, 6):
        h = hmac.new(shared_key, combined + bytes([i]), hashlib.sha1)
        data += h.digest()

    challenge = hmac.new(data[:20], combined, hashlib.sha1).digest()
    send_key = data[20:52]
    recv_key = data[52:84]

    logger.info("🔐 Derived keys and challenge:")
    logger.info(f"challenge: {challenge.hex()}")
    logger.info(f"send_key:  {send_key.hex()}")
    logger.info(f"recv_key:  {recv_key.hex()}")

    return challenge, send_key, recv_key

def verify_server_signature(gs: bytes, signature: bytes) -> bool:
    logger.info("🧪 Verifying server signature")
    logger.info(f"gs.len: {len(gs)}")
    logger.info(f"gs: {gs.hex()}")
    logger.info(f"sig.len: {len(signature)}")
    logger.info(f"sig: {signature.hex()}")
    logger.info(f"SERVER_KEY.len: {len(SERVER_KEY)}")
    logger.info(f"server gs (len={len(gs)}): {gs.hex()}")

    public_numbers = rsa.RSAPublicNumbers(
        e=65537,
        n=int.from_bytes(SERVER_KEY, byteorder='big')
    )
    public_key = public_numbers.public_key(default_backend())

    # ⚠️ DO NOT hash manually! Let cryptography hash it as part of the verify() call.
    try:
        public_key.verify(
            signature,
            gs,  # pass raw gs
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        logger.info("✅ RSA signature verified")
        return True
    except InvalidSignature:
        logger.error("❌ RSA signature verification failed — INVALID SIGNATURE")
        return False
    except Exception as e:
        logger.exception("💥 Unexpected error during RSA verification")
        return False

def parse_ap_response(raw_bytes: bytes):
    if len(raw_bytes) < 4:
        raise ValueError("Invalid response: too short for length prefix")

    length = int.from_bytes(raw_bytes[:4], "big")
    payload = raw_bytes[4:]

    if len(payload) != length:
        logger.warning(f"⚠️ APResponseMessage length mismatch: header={length}, actual={len(payload)}")

    response = keyexchange_pb2.APResponseMessage()
    response.ParseFromString(payload)
    logger.info("✅ Parsed APResponseMessage:")
    logger.info(text_format.MessageToString(response))

    dh = response.challenge.login_crypto_challenge.diffie_hellman


    server_key = dh.gs
    server_signature = dh.gs_signature


    return {
        "server_key": server_key,
        "server_signature": server_signature,
        "response_message": response,
        "raw_bytes": raw_bytes,
    }

# --- Helper Functions ---
def generate_dh_keypair():
    from Crypto.Util import number
    private_key = number.getRandomRange(2, DH_P - 2)
    public_key = pow(DH_G, private_key, DH_P)

    # 🧠 Critical: use minimal-length byte representation
    public_key_bytes = public_key.to_bytes((public_key.bit_length() + 7) // 8, byteorder='big')
    return private_key, public_key_bytes


async def open_tcp_connection_nodelay(host, port):
    loop = asyncio.get_event_loop()
    rsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    rsock.setblocking(False)
    await loop.sock_connect(rsock, (host, port))
    return await asyncio.open_connection(sock=rsock)


def compute_shared_secret(private_key, peer_public):
    return pow(peer_public, private_key, DH_P)


def build_and_pack_client_hello(public_key_bytes):
    hello = keyexchange_pb2.ClientHello()

    build_info = keyexchange_pb2.BuildInfo()
    build_info.product = keyexchange_pb2.Product.PRODUCT_CLIENT
    build_info.platform = keyexchange_pb2.Platform.PLATFORM_OSX_X86
    build_info.version = 124200290
    build_info.product_flags.append(keyexchange_pb2.ProductFlags.PRODUCT_FLAG_NONE)
    hello.build_info.CopyFrom(build_info)

    hello.cryptosuites_supported.append(keyexchange_pb2.Cryptosuite.CRYPTO_SUITE_SHANNON)


    dh = hello.login_crypto_hello.diffie_hellman
    dh.gc = public_key_bytes
    dh.server_keys_known = 1

    hello.client_nonce = os.urandom(16)
    hello.padding = b'\x1e'


    message_data = hello.SerializeToString(deterministic=True)

    full_payload = message_data

    return full_payload

def build_and_pack_client_response(shared_secret: bytes) -> bytes:
    # This step is CRITICAL: hash the shared secret first
    key = hashlib.sha1(shared_secret).digest()

    # Then HMAC the string "Client response" using that key
    hmac_value = hmac.new(key, b"Client response", hashlib.sha1).digest()

    response = keyexchange_pb2.ClientResponsePlaintext()
    response.login_crypto_response.diffie_hellman.hmac = hmac_value
    response.pow_response = keyexchange_pb2.PoWResponseUnion()
    response.crypto_response = keyexchange_pb2.CryptoResponseUnion()
    return response.SerializeToString(deterministic=True)


# --- TCP Connection and Mercury Handshake ---
async def mercury_tcp_handshake(ap_address: str, token: str, port: int = 4070 ):
    logger.info("Connecting to AP via TCP: %s:%d", ap_address, port)

    reader, writer = await open_tcp_connection_nodelay(ap_address, port)

    # Build and send ClientHello
    private_key, public_key_bytes = generate_dh_keypair()
    payload = build_and_pack_client_hello(public_key_bytes)
    prefix = b"\x00\x04"
    packet_len = len(prefix) + 4 + len(payload)
    length = packet_len.to_bytes(4, "big")
    full_payload = prefix + length + payload
    writer.write(full_payload)

    with open("clienthello_py.raw", "wb") as f:
        f.write(full_payload)

    await writer.drain()
    logger.info("✅ Sent ClientHello")

    try:
        peek = await asyncio.wait_for(reader.read(4096), timeout=5)
        if peek:
            logger.info(f"📥 Received {len(peek)} bytes from server")
            with open("server_mid_response.raw", "wb") as f:
                f.write(peek)
        else:
            logger.warning("📭 Server sent an empty response")
    except asyncio.TimeoutError:
        logger.error("❌ Timeout waiting for any server response")
        return
    except Exception as e:
        logger.exception(f"💥 Unexpected error while reading server response: {e}")

    parsed = parse_ap_response(peek)
    server_key_bytes = parsed["server_key"]
    server_signature = parsed["server_signature"]

    if not verify_server_signature(server_key_bytes, server_signature):
        logger.error("❌ Server signature invalid, aborting handshake.")
        writer.close()
        await writer.wait_closed()
        return

    logger.info("✅ Server key signature verified. Proceeding with key derivation.")

    server_public_int = int.from_bytes(server_key_bytes, byteorder="big")
    shared_key_int = compute_shared_secret(private_key, server_public_int)
    shared_key_bytes = shared_key_int.to_bytes((shared_key_int.bit_length() + 7) // 8, 'big')

    challenge, send_key, recv_key = derive_keys(
        shared_key=shared_key_bytes,
        client_hello=full_payload,
        ap_response=parsed["raw_bytes"]
    )

    shannon = SpotifyShannon(send_key, recv_key)
    logger.info("🔐 Shannon session ready")

    response = keyexchange_pb2.ClientResponsePlaintext()
    response.login_crypto_response.diffie_hellman.hmac = challenge
    response.pow_response.SetInParent()
    response.crypto_response.SetInParent()
    response_payload = response.SerializeToString(deterministic=True)

    writer.write(len(response_payload).to_bytes(4, "big") + response_payload)
    logger.info("📤 ClientResponsePlaintext size: %d", len(response_payload))
    logger.info("📤 ClientResponsePlaintext raw: %s", response_payload.hex())
    await writer.drain()
    logger.info("✅ Sent ClientResponsePlaintext")

    # After sending ClientResponsePlaintext
    try:
        final_ack = await asyncio.wait_for(reader.readexactly(9), timeout=5)
        logger.info(f"📥 Final login ack (raw 9 bytes): {final_ack.hex()}")

        ack_response = final_ack[4:]

        if ack_response[:3] == b'\xf2\x01\x02':
            logger.info("✅ Server accepted ClientResponse — we are now logged in!")
            await send_mercury_get(shannon, writer, "hm://identity/v3/me", token)
        else:
            logger.warning(f"⚠️ Unexpected login ack format: {ack_response.hex()}")

    except asyncio.TimeoutError:
        logger.error("❌ Timeout waiting for login acknowledgement")
        writer.close()
        await writer.wait_closed()
        return

    try:
        while True:
            encrypted_header = await reader.readexactly(3)
            payload_length = int.from_bytes(encrypted_header[1:3], 'big')
            encrypted_rest = await reader.readexactly(payload_length + 4)
            full_packet = encrypted_header + encrypted_rest

            logger.info(f"📦 Raw encrypted packet: {full_packet.hex()}")

            try:
                decrypted = shannon.decrypt_packet(full_packet)
                cmd = decrypted[0]
                body = decrypted[1:]

                logger.info(f"🎧 Got command: {cmd:#04x} ({len(body)} bytes)")

                if cmd == 0x09:
                    logger.info("🎉 Successfully logged in — ready to subscribe to PlayerState!")
                elif cmd == 0x1b:
                    logger.info("📡 Got Ping")
                elif cmd == 0x1e:
                    logger.info("📶 PlayerState or Mercury data")
                    logger.debug(body.hex())
                else:
                    logger.info(f"📨 Unknown command {cmd:#04x}")
                    logger.debug(body.hex())

            except ValueError as e:
                logger.error(f"⚠️ Failed to decrypt packet: {e}")
                break

    except asyncio.IncompleteReadError:
        logger.warning("📴 Connection closed by server")


async def send_mercury_get(shannon: SpotifyShannon, writer: asyncio.StreamWriter, uri: str, token: str):
    cmd = "GET"
    packet = build_mercury_packet(cmd, uri, token)
    encrypted = shannon.encrypt_packet(packet)
    writer.write(encrypted)
    await writer.drain()
    logger.info(f"📤 Sent Mercury GET to {uri} with token")


def build_mercury_header_payload(headers: dict) -> bytes:
    header_group = mercury_pb2.HeaderGroup()
    for key, value in headers.items():
        h = header_group.headers.add()
        h.key = key
        h.value = value.encode()
    return header_group.SerializeToString()


def build_mercury_packet(cmd: str, uri: str, token: str) -> bytes:
    header = mercury_pb2.Header()
    header.uri = uri
    header.method = cmd  # should be "GET"
    header.content_type = "application/vnd.spotify.identity+json"

    # Add extra user fields, as observed in Librespot's packet:
    uf_auth = header.user_fields.add()
    uf_auth.key = "Authorization"
    uf_auth.value = f"Bearer {token}".encode("utf-8")

    uf_client_version = header.user_fields.add()
    uf_client_version.key = "X-Spotify-Client-Version"
    uf_client_version.value = b"124200290"  # use the version Librespot sends

    uf_device = header.user_fields.add()
    uf_device.key = "X-Spotify-Device"
    uf_device.value = b"python_device_001"  # change this to your actual device id if available

    uf_user_agent = header.user_fields.add()
    uf_user_agent.key = "X-Spotify-User-Agent"
    uf_user_agent.value = b"UniversalScrobbler/1.0"  # adjust as needed

    header_bytes = header.SerializeToString()

    # Build the MercuryMultiGetRequest payload with one MercuryRequest.
    mercury_req = mercury_pb2.MercuryRequest()
    mercury_req.uri = uri
    mercury_req.content_type = "application/vnd.spotify.identity+json"
    mercury_req.body = b""   # Explicitly set as empty
    mercury_req.etag = b""   # Explicitly set as empty

    multi_req = mercury_pb2.MercuryMultiGetRequest()
    multi_req.request.append(mercury_req)
    multi_req_bytes = multi_req.SerializeToString()

    # Assemble the full packet (note the leading command byte and header length).
    packet = b'\x4A' + len(header_bytes).to_bytes(2, 'big') + header_bytes + multi_req_bytes
    return packet



async def do_mercury_handshake_for_user(user_uuid: str):
    logger.info("Starting TCP Mercury handshake for user %s", user_uuid)
    engine = get_async_engine()
    async with AsyncSession(engine) as session:
        token = await spotify_service.get_token_for_user(user_uuid, session)
        logger.info(token)
        logger.info("Token: %s...", token[:8])
        ap_address = "ap-gew4.spotify.com"

        await mercury_tcp_handshake(ap_address, token)


if __name__ == "__main__":
    asyncio.run(do_mercury_handshake_for_user("b37ece05-656e-4acc-9c18-c03d20918060"))