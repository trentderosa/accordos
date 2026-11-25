# AccordOS architecture (simulator + trips + health + voice intents)

## Data flow (today)

```
SimulatorProvider → TelemetryService → TripService (state machine)
       │                  ↓                    ↓
       │       FastAPI REST + WS         SQLite (schema v3)
       │                  ↓                    ↓
       └─ read_dtcs() → HealthService   diagnostics / trends / reminders
                          ↓
              GET /api/health, /api/maintenance, /api/sync
              VoiceService ← telemetry + trips + health
                          ↓
              POST /api/voice/command, GET /api/voice/briefing
                          ↓
              React PWA → IndexedDB trip replica + glance cache
              Parked: Recent trips + Vehicle health + Voice lab
```

Root JSON and OpenAPI live on the backend (`/`, `/docs`). Frontend never talks to the vehicle directly.

- `TelemetryProvider` is the swap point for a future read-only OBD adapter (`read_dtcs()` included).
- Trip state machine: idle → starting → active → ending → finalized/recovered.
- SQLite under `backend/storage/` (migrations to v3): trips (+ revision), samples, checkpoints, sync_meta, diagnostic_events, telemetry_trend_samples, trend_state, maintenance_reminders, health_alerts.
- Sync is Pi-authoritative with monotonic revisions and idempotent upserts by stable trip id.
- Health explains DTCs via vetted static reference data; distinguishes code vs diagnosis; never clears codes.
- Trend alerts use documented thresholds with hysteresis to reduce flicker.
- IndexedDB stores last telemetry glance plus synced trip history for offline UI.
- Dev servers bind `0.0.0.0` by default for same-LAN iPhone testing; CORS allows localhost + RFC1918 only.
- Voice routes allowlisted intents only (local-or-bearer); never shell, never vehicle controls. See [voice-intents.md](./voice-intents.md).

## Modules

| Path | Role |
|---|---|
| `simulator/` | `SimulatorProvider` — drive cycle + demo scenarios |
| `backend/telemetry/` | `TelemetryProvider` ABC, `TelemetrySample`, `TelemetryService` (poll + WS fan-out) |
| `backend/trips/` | State machine, efficiency scaffold, repository, `TripService` |
| `backend/storage/` | SQLite `Database` + migrations (v3) |
| `backend/api/` | REST + WebSocket routes |
| `backend/health/` | Read-only DTC explanations, trends, maintenance |
| `backend/voice/` | Deterministic intent router, ~15s context, briefing, local-or-bearer auth |
| `frontend/` | React PWA dashboard, hooks, IndexedDB replica + glance, Voice lab |
| `deploy/` | Pi systemd / env placeholders (Phase 2+) |
| `tests/` | pytest coverage for simulator, trips, sync, health, voice, API |

App wiring: `backend/main.py` → `create_app()` constructs DB, `TripService` (recover on start), `HealthService`, `VoiceService`, `TelemetryService(SimulatorProvider, on_sample=trips+health)`.

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

## What is intentionally stubbed / gated

- Voice: **intent routing + text Voice lab done**; wake word, ASR, TTS, and iPhone PWA background audio remain open (audio feasibility gate).
- Maps / Spotify: encoded deep-link + open/Siri **stubs** (see [infotainment.md](./infotainment.md)); verified launches / OAuth PKCE later with owner approval; never fabricate map/police data.
- Trusted HTTPS CA: later phases.
- Real OBD: unverified; no provider in-tree yet. Health uses simulated DTC scenarios today.
