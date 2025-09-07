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

- [x] Provision Redis (with persistence + backoff reconnect).
- [x] Integrate Redis client (async) with one subscriber per worker.
- [x] Message schema → tiny payloads `{ rev, type, ts }`.
- [ ] Publish on commit → we now publish inline after DB ops (improve later).
- [x] Subscriber fan-out with per-user queues, latest-wins policy.
- [x] SSE endpoint with snapshot on connect + heartbeats.
- [ ] Edge / proxy tuning (`proxy_buffering off`, timeouts).
- [ ] Gunicorn multi-worker validation.

---

## 2. Authoritative Session State & Control Model

- [x] DB table `playback_session` with `play_state`, `position_ms`, `active_device`, `updated_at`.
- [ ] Projection of `position_ms` via monotonic clock math.
- [x] Routes: `/playback-sessions/play`, `/pause`, `/resume`, `/seek`, `/next`, `/previous`.
- [ ] Speaker switching (`/playback-sessions/speaker`) not yet wired.
- [x] Events over SSE: timeline updates with `now_playing`, `file_url`, `duration_ms`, `play_state`, `position_ms`.
- [ ] Idempotence with client event UUID (future).

---

## 3. Device Management

- [ ] DB: devices table for `device_uuid`, `name`, `last_seen`.
- [ ] Routes: `/devices/register`, `/devices/heartbeat`.
- [ ] UI: choose active speaker → rotate token + update session.

---

## 4. Seekable FLAC File Proxy (Range)

- [x] Endpoint `/music/file/{collection_track_uuid}` returns `FileResponse` with `Accept-Ranges: bytes`.
- [ ] Full Range handling (`206 Partial Content`, `416`).
- [ ] Token model (bind to `{user, session, device, track}` with TTL).
- [ ] Perf: Nginx `auth_request` + `sendfile`.

---

## 5. Queue Management & Player Controls

- [x] DB: playback_queue already in place.
- [ ] Fix auto-advance: next clears queue but playback doesn’t sync → must reconcile.
- [x] Play/Pause/Resume working.
- [x] Seek wired client ↔ server.
- [ ] Like events, shuffle, repeat_mode missing.
- [ ] Better enqueue API (`/queue/enqueue` list of tracks/albums).

---

## 6. Persistence & Resume

- [x] Persist session state (`play_state`, `position_ms`, `active_device`, etc.).
- [ ] On login: fetch snapshot, resume at projected position.
- [ ] Staleness rules: reset old snapshots.

---

## 7. Testing (Unit, Integration, E2E)

- [ ] Unit tests for revision math, range handling.
- [ ] Integration: Redis fan-out, reconnect correctness.
- [ ] E2E: two devices controlling same session, speaker switching, like events.