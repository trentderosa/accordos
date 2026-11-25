# AccordOS architecture (simulator + trip intelligence + sync)

## Data flow (today)

```
SimulatorProvider → TelemetryService → TripService (state machine)
                         ↓                    ↓
              FastAPI REST + WS         SQLite (schema v2)
                         ↓                    ↓
              GET /api/sync?cursor=     revision upserts
                         ↓
              React PWA → IndexedDB trip replica + glance cache
              Parked “Recent trips” ← replica (offline after sync)
              Export JSON/CSV ↔ restore
```

Root JSON and OpenAPI live on the backend (`/`, `/docs`). Frontend never talks to the vehicle directly.

- `TelemetryProvider` is the swap point for a future read-only OBD adapter.
- Trip state machine: idle → starting → active → ending → finalized/recovered.
- SQLite under `backend/storage/` (migrations to v2): `trips` (+ `revision`), `trip_samples`, `trip_checkpoints`, `sync_meta`.
- Sync is Pi-authoritative with monotonic revisions and idempotent upserts by stable trip id.
- Efficiency score is a scaffold with proposed weights; withheld when confidence is low.
- IndexedDB stores last telemetry glance plus synced trip history for offline UI.
- Dev servers bind `0.0.0.0` by default for same-LAN iPhone testing; CORS allows localhost + RFC1918 only.
- Voice / health / maintenance endpoints are stubs that never issue vehicle commands.

## Modules

| Path | Role |
|---|---|
| `simulator/` | `SimulatorProvider` — drive cycle + demo scenarios |
| `backend/telemetry/` | `TelemetryProvider` ABC, `TelemetrySample`, `TelemetryService` (poll + WS fan-out) |
| `backend/trips/` | State machine, efficiency scaffold, repository, `TripService` |
| `backend/storage/` | SQLite `Database` + migrations (v2) |
| `backend/api/` | REST + WebSocket routes |
| `backend/health/` | Read-only DTC/maintenance **stubs** |
| `backend/voice/` | Deterministic intent **stub** (no shell execution) |
| `frontend/` | React PWA dashboard, hooks, IndexedDB replica + glance |
| `deploy/` | Pi systemd / env placeholders (Phase 2+) |
| `tests/` | pytest coverage for simulator, trips, sync, API |

App wiring: `backend/main.py` → `create_app()` constructs DB, `TripService` (recover on start), `TelemetryService(SimulatorProvider, on_sample=trips.ingest)`.

## TelemetryProvider swap (simulator → future OBD)

Contract (`backend/telemetry/provider.py`):

- `connect()` / `disconnect()`
- `read() → TelemetrySample`
- `capabilities() → dict` (metrics, `read_only: true`)
- `is_connected()`

**Today:** `SimulatorProvider` (`source="simulator"`, `simulated=True`, scenarios via `/api/simulator/scenario`).

**Future:** a read-only OBD provider implementing the same ABC:

- Explicit **allowlist** of diagnostic requests / PIDs.
- Never clear codes, reset ECUs, or issue control commands.
- Map unsupported PIDs to `quality="unavailable"` — do not invent values.
- `create_app(provider=ObdProvider(...))` (or env-selected factory) is the intended injection point; trip engine and API stay unchanged.

`NullProvider` exists as a disconnected placeholder.

## Trip intelligence

State machine: `idle → starting → active → ending → finalized` (or `recovered` after interruption).

- Engine-running evidence: RPM + communication quality with debounce.
- Trips **never** end solely because speed is 0.
- Continuous samples + periodic checkpoints; incomplete rows recovered on process start.
- Efficiency score: proposed weights; withheld when confidence is low (not a safety rating).

Authoritative store is SQLite on the host (Pi later). Phone IndexedDB holds a synced trip replica plus glance cache. Sync: `GET /api/sync?cursor=...` — see [api.md](./api.md) and [trip-intelligence.md](./trip-intelligence.md).

## Networking model

- Dev: uvicorn + Vite on `0.0.0.0`; CORS = localhost + RFC1918 regex.
- Phone → Vite (or future nginx) → proxy `/api` and `/ws` to backend.
- Production Pi sketch: systemd for uvicorn + reverse proxy; still **local-only**. See [security-and-power.md](./security-and-power.md).

## What is intentionally stubbed

- Health / maintenance: empty lists + honest notes.
- Voice: fixed replies for a small intent set; unknown → graceful failure.
- Maps / Spotify / wake word / trusted HTTPS CA: later phases.
- Real OBD: unverified; no provider in-tree yet.
