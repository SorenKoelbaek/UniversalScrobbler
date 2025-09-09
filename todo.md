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

## 0. Current Bugs:

- [ ] add to queue doesn't enforce album track order
- [ ] login doesn't redirect to discover
- 
## 1. Redis for Multi-Worker SSE

- [x] Provision Redis + async client.
- [x] Pub/sub channel per user with tiny payload schema `{ rev, type, ts }`.
- [x] Subscriber fan-out with per-user queues, latest-wins.
- [x] SSE endpoint with snapshot on connect + heartbeats.
- [ ] Edge / proxy tuning (`proxy_buffering off`, timeouts).
- [ ] Validate Gunicorn multi-worker behavior.

---

## 2. Authoritative Session State & Control Model

- [x] DB table `playback_session` with `play_state`, `position_ms`, `active_device`, `updated_at`.
- [x] Routes: `/playback-sessions/play`, `/pause`, `/resume`, `/seek`, `/next`, `/previous`.
- [x] SSE timeline updates include `now_playing`, `file_url`, `duration_ms`, `play_state`, `position_ms`.
- [ ] Projection of `position_ms` via monotonic clock math.
- [x] Speaker switching (`/playback-sessions/speaker`).
- [ ] Idempotence with client event UUID.

---

## 3. Device Management

- [x] DB: devices table (`device_uuid`, `name`, `last_seen`).
- [x] Devices now auto-registered on connect (via _get_or_create_session)
- [x] Routes: /devices/register, /devices/heartbeat (not explicit, piggybacking on session/stream now)
- [x] UI: choose active speaker → device list + switch endpoint integrated today

---

## 4. Seekable FLAC File Proxy (Range)

- [x] `/music/file/{library_track_uuid}` returns `FileResponse` with `Accept-Ranges: bytes`.
- [ ] Full Range handling (`206 Partial Content`, `416`).
- [ ] Token model (bind to `{user, session, device, track}` with TTL).
- [ ] Perf: Nginx `auth_request` + `sendfile`.

---

## 5. Queue Management & Player Controls

- [x] Queue + playback working end-to-end.
- [x] Play/Pause/Resume wired.
- [x] Seek wired client ↔ server.
- [ ] Auto-advance: sync playback + clear queue.
- [ ] Like events, shuffle, repeat modes.
- [ ] Bulk enqueue API (`/queue/enqueue` list of tracks/albums).

---

## 6. Persistence & Resume

- [x] Persist session state in DB.
- [ ] On login: fetch snapshot and resume position.
- [x] Staleness rules: override stale active_device_uuid with connected device (fixed today)

---

## 7. Search & Metadata

- [x] Unified search across albums, artists, tracks.
- [x] `has_digital` flag applied to albums/tracks/artists.
- [ ] Optimize queries for fewer roundtrips (bulk joins).
- [ ] Improve tag/genre enrichment in search.

---

## 8. Frontend Updates

- [x] Discover page → landing page:
  - Union `albums[] + artists[*].albums + tracks[*].albums` → distinct → render AlbumCards.
  - Show only items with `has_digital=true` by default.
  - Debounced search calls `/music/search`.
- [x] Player UI:
  - Show play/pause/seek/next/prev controls bound to new endpoints.
  - Show devices and allow switching active speaker.
- [x] Devices shown + switching active speaker
- [ ] Collection page: infinite scroll + sort refinements.

---

## 9. Testing (Unit, Integration, E2E)

- [ ] Unit tests: revision math, range handling.
- [ ] Integration: Redis fan-out, reconnect correctness.
- [ ] E2E: two devices controlling same session, speaker switching, queue advance, like events.
