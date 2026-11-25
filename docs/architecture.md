# AccordOS architecture

## Data flow (today)

```
SimulatorProvider ──read()──► TelemetryService ──on_sample──► TripService
                                      │                           │
                                      │                           ▼
                                      │                     SQLite (schema v1)
                                      │                   trips / samples / checkpoints
                                      ▼
                            FastAPI REST + WS /ws/telemetry
                                      │
                                      ▼
                            React PWA (Vite)
                              ├─ live gauges + connection UX
                              ├─ parked Recent trips ← GET /api/trips
                              └─ IndexedDB last-sample glance (offline UI)
```

Root JSON and OpenAPI live on the backend (`/`, `/docs`). Frontend never talks to the vehicle directly.

## Modules

| Path | Role |
|---|---|
| `simulator/` | `SimulatorProvider` — drive cycle + demo scenarios |
| `backend/telemetry/` | `TelemetryProvider` ABC, `TelemetrySample`, `TelemetryService` (poll + WS fan-out) |
| `backend/trips/` | State machine, efficiency scaffold, repository, `TripService` |
| `backend/storage/` | SQLite `Database` + migrations (v1) |
| `backend/api/` | REST + WebSocket routes |
| `backend/health/` | Read-only DTC/maintenance **stubs** |
| `backend/voice/` | Deterministic intent **stub** (no shell execution) |
| `frontend/` | React PWA dashboard, hooks, IndexedDB |
| `deploy/` | Pi systemd / env placeholders (Phase 2+) |
| `tests/` | pytest coverage for simulator, trips, API |

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

Authoritative store is SQLite on the host (Pi later). Phone IndexedDB is a **glance cache**, not the trip journal of record. Sync scaffold: `GET /api/sync?cursor=...` — see [api.md](./api.md) and [trip-intelligence.md](./trip-intelligence.md).

## Networking model

- Dev: uvicorn + Vite on `0.0.0.0`; CORS = localhost + RFC1918 regex.
- Phone → Vite (or future nginx) → proxy `/api` and `/ws` to backend.
- Production Pi sketch: systemd for uvicorn + reverse proxy; still **local-only**. See [security-and-power.md](./security-and-power.md).

## What is intentionally stubbed

- Health / maintenance: empty lists + honest notes.
- Voice: fixed replies for a small intent set; unknown → graceful failure.
- Maps / Spotify / wake word / trusted HTTPS CA: later phases.
- Real OBD: unverified; no provider in-tree yet.
