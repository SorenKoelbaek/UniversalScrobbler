# UniversalScrobbler Roadmap / TODO

> **Scope:**  
> This todo covers the implementation of audio file playback. UniversalScrobbler (this FastAPI application) handles **auth**, **state**, **SSE fan-out**, **device control**, and **seekable FLAC file proxying** (no transcoding).  
> Exactly **one active playback device** at a time; **all devices can control**.  
> Seek supported via **Range-enabled file transport**.  
> Devices **connect and authenticate**, and can then be chosen as the **active speaker**.  
> UI shows playback state, allows **play/pause/seek/next/prev**, and **device switching**.  
> UniversalScrobbler is deployed to **Ubuntu**, behind **Nginx + Gunicorn** (Uvicorn workers).  
> We use **SSE** for real-time updates.  
> UniversalScrobbler has the FLAC directory mounted at **`/mnt/Music`** and mapped to the music catalog. File serving is done via **short-lived, user-tied proxy URLs** that require authentication.

---

### Prompt instructions for consistency and completeness

- Routes are managed using files in `api/routers/`.
- Redis plan includes pub/sub. **Channel per user:** `us:user:{user_uuid}`. **Message shape (tiny):** `{ "rev": <int>, "type": "timeline|speaker|queue|like|options", "ts": <ms> }`. Keep payloads small; clients fetch full state via `GET /sessions/{user_id}` if needed.
- **Publish flow:** Apply state change in DB/memory and bump `rev`. Publish on `us:user:{uuid}` with the new `rev` (coalesce multiple changes in one request → single publish). SSE workers that have clients for that user receive and forward.
- Database is configured using **SQLAlchemy** and **Alembic** for migration, and **async sessions**. Example model is from `models/sqlmodels.py`:

```python
class Collection(SQLModel, table=True):
    __tablename__ = "collection"
    collection_uuid: UUID = Field(default_factory=uuid4, primary_key=True)
    collection_name: str
    user_uuid: UUID = Field(foreign_key="appuser.user_uuid")
    user: Optional["User"] = Relationship(back_populates="collections")
    albums: List["Album"] = Relationship(link_model=CollectionAlbumBridge)
    album_releases: List["AlbumRelease"] = Relationship(
        link_model=CollectionAlbumReleaseBridge
    )
    tracks: List["CollectionTrack"] = Relationship(back_populates="collection")
    created_at: datetime = Field(
        default_factory=now_utc_naive,
        sa_column_kwargs={"server_default": func.now()}
    )
```

- Application is deployed to Ubuntu server automatically on merge to main, run with `uvicorn.service`. Database is **Postgres**.
- FLACs live in **`/mnt/Music`**.
- For collaboration:
  - Replies must be **short, consistent, easy to understand**.
  - **Never assume**; prefer extra steps over ambiguity.
  - For code, provide **one step at a time** to allow course correction.

---

## 1. Add Redis for Multi-Worker SSE

**Goal:** SSE must work with multiple Gunicorn workers.

- [x] **Provision Redis**
  - Single node to start; enable **RDB/AOF** persistence as needed.
  - Health checks + connection limits sized for expected SSE fan-out.
  - Add a **readiness check** in the app (subscriber reconnect with backoff).

- [x] **Integrate Redis client (async)**
  - One **long-lived subscriber** task per worker process.
  - Channels: **per-user** `us:user:{user_uuid}` (tiny payloads only).

- [x] **Message schema**
  - `{ "rev": <int>, "type": "timeline|speaker|queue|like|options", "ts": <ms> }`
  - `rev` is **monotonically increasing per user** (idempotence).

- [ ] **Publish on commit**
  - Coalesce multiple state changes in a request → **one** publish after **DB commit**.

- [x] **Subscriber fan-out**
  - If worker has SSE clients for that user: enqueue to **bounded** per-client queue (e.g., 50).
  - If queue full: **drop oldest** → **latest-wins** policy.

- [x] **SSE endpoint**
  - On connect: send **immediate snapshot** (`GET /sessions/{user_id}`) then start deltas.
  - Keepalive: heartbeat `:\n\n` every **5–15s**.
  - On disconnect: remove client queue cleanly.
  - Set headers: `Cache-Control: no-store`, `X-Accel-Buffering: no`, `Content-Type: text/event-stream`.

- [ ] **Edge / proxy**
  - `/events`: `proxy_buffering off`, long `proxy_read_timeout`, HTTP/1.1 keep-alive.

- [ ] **Gunicorn**
  - Use `uvicorn.workers.UvicornWorker`; run **multiple workers** (Redis ensures cross-worker delivery).

**Security (baked-in):**
- Redis credentials/TLS configured; app uses least-privileged creds.
- SSE route requires authenticated user; map connection → `user_uuid` **server-side** (do not trust client params).

---

## 2. Authoritative Session State & Control Model

**Goal:** Single source of truth per user; deterministic cross-device behavior.

- [ ] **DB table: session state (one row per user)**
  - `active_device_uuid`, `track_uuid`, `position_ms`, `play_state` (`playing|paused|stopped`),
  - `last_update_mono`, `revision`, `updated_at`,
  - **Playback options:** `shuffle` (bool), `repeat_mode` (enum: `off|one|all`).

- [ ] **Projection**
  - `projected_position = position_ms + (now_mono - last_update_mono)` **iff** `play_state=playing`.

- [ ] **Routes (contracts)**
  - `GET /sessions/{user_uuid}` → snapshot (hydration + reconnect).
  - `POST /sessions/{user_uuid}/speaker` → set `active_device_uuid`, bump `revision`, **publish**.
  - `POST /sessions/{session_uuid}/play` / `pause` / `seek`
  - `POST /sessions/{session_uuid}/next` / `prev`
  - `POST /sessions/{session_uuid}/options` → update `shuffle` and `repeat_mode`.

- [ ] **Events over SSE**
  - `timeline_update` (play/pause/seek/next/prev)
  - `speaker_change`
  - `options_change` (shuffle/repeat)
  - `like` (track liked)
  - `timeline_beacon` every **3–5s** when clients connected

- [ ] **Idempotence**
  - Accept `client_event_uuid`; ignore duplicates per `revision`.

**Security (baked-in):**
- All routes OAuth2-protected; authorize user ↔ session ownership.
- Input validation for `repeat_mode ∈ {off, one, all}`; rate-limit control routes.

---

## 3. Device Management

**Goal:** Enumerate devices, choose active speaker, show presence.

- [ ] **DB: devices**
  - `device_uuid`, `device_name`, `user_uuid`, `last_seen`, `device_platform` (optional).

- [ ] **Routes**
  - `POST /devices/register` (id + friendly name).
  - `PATCH /devices/heartbeat` (presence; update `last_seen`).
  - UI lists devices; **Choose speaker** triggers `/sessions/{user_id}/speaker`.

**Security (baked-in):**
- Device register/heartbeat require authenticated user; enforce ownership.
- On `/speaker`, rotate media token material (see Step 4).

---

## 4. Seekable FLAC File Proxy (Range)

**Goal:** Native scrubbing in UI; one active device gets playable bytes.

- [ ] **Endpoint** `GET /media/tracks/{track_id}?token=…`
  - Always return `Accept-Ranges: bytes` (even on 200).
  - Support `206 Partial Content` and `416 Range Not Satisfiable`.
  - Headers:
    - `Content-Type: audio/flac`
    - `Cache-Control: no-store`
    - `Content-Length` on full responses.

- [ ] **Token model**
  - Bind to `{user_id, session_id, active_device_id, track_id}`.
  - TTL 60–120s; **rotate immediately** on `/speaker` change.
  - Only active device can refresh tokens continuously.

- [ ] **Optional perf**
  - Front with Nginx `auth_request` + `sendfile` for zero-copy streaming.

**Security (baked-in):**
- Verify token binding and expiry; check user’s access to `track_id`.
- Log and rate-limit token mint attempts; revoke on suspicious activity.

---

## 5. Queue Management & Player Controls

**Goal:** Ordered playback with additional UX controls.

- [ ] **DB: queue**
  - Per user: `idx`, `track_id`, `status` (`queued|playing|played|failed`).

- [ ] **Enqueue API**
  - `/queue/enqueue` accepts list of `track_id` (or album → tracks).
  - Validate availability; set initial `status=queued`.

- [ ] **Next/Prev & auto-advance**
  - `/sessions/{session_id}/next` / `/prev` manipulate queue pointer.
  - On client `ended` event: mark `played`, move to next (respect `repeat_mode` and `shuffle`).

- [ ] **Play/Pause toggle**
  - Provide `/sessions/{session_id}/toggle` (server flips `play↔pause`, bumps `revision`).

- [ ] **Like event**
  - `/tracks/{track_id}/like` raises “like” (update `likes` table or event log) and publishes `like` event over SSE for UI sync.

- [ ] **Shuffle & Repeat**
  - `shuffle` (bool) stored in session; when true, maintain a **session-scoped permutation**.
  - `repeat_mode` enum:
    - `off`: stop at end of queue,
    - `one`: repeat current track,
    - `all`: loop queue (respect current shuffle order).
  - `/sessions/{session_id}/options` updates these; publish `options_change`.

**Security (baked-in):**
- Enqueue/like routes require user auth; validate track ownership/visibility.
- Guard against excessive queue mutations (rate-limit).

---

## 6. Persistence & Resume

**Goal:** Restore user state across logins/devices.

- [ ] **Persist snapshot** on every control change:
  - `track_id`, `position_ms`, `play_state`, `active_device_id`,
  - `shuffle`, `repeat_mode`, `updated_at`, `revision`.

- [ ] **On login**
  - Client fetches `GET /sessions/{user_id}`.
  - If no active playback, display **paused** at last `track_id` + `position_ms`.

- [ ] **Staleness**
  - If snapshot older than e.g. 24h, reset to paused at `position_ms=0` (keep track selection).

**Security (baked-in):**
- Snapshot read/write limited to the user; redact PII in logs.
- Defensive checks to avoid resurrecting stale tokens on resume.

---

## 7. Testing (Unit, Integration, E2E)

**Goal:** Validate correctness under multi-worker and multi-device conditions.

- [ ] **Unit**
  - Revision math and projection accuracy.
  - `repeat_mode` + `shuffle` semantics at queue boundaries.
  - Range handling (`206/416`) and token binding/TTL.

- [ ] **Integration**
  - Multi-worker SSE fan-out through Redis.
  - Disconnect/reconnect → snapshot rehydrate correctness.
  - Burst of seeks/controls → coalesced publish (one per request).

- [ ] **E2E**
  - Two devices: **Choose speaker**, play, seek, toggle pause/play → both UIs stay in sync; only active device plays audio.
  - Switch speaker mid-track → new device starts at **projected** position.
  - Like events sync instantly across devices.
