# AccordOS architecture (simulator + OBD stub + trips + health + voice)

## Data flow (today)

```
TelemetryProvider (SIMULATOR | OBD stub)
       │
       ├─ SimulatorProvider → drive cycle + demo scenarios
       └─ ObdProvider stub  → "adapter not connected" (Sunday: python-OBD)
       │
       ↓
TelemetryService → TripService (state machine)
       │                  ↓
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

- `TelemetryProvider` is the swap point (`connect`, `disconnect`, `discover_capabilities`, allowlisted `read`, never write/clear).
- Provider selection: `ACCORDOS_PROVIDER=SIMULATOR|OBD` via `build_provider()` — see [obd-provider.md](./obd-provider.md).
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
| `backend/telemetry/` | ABC, allowlist, `ObdProvider` stub, factory, `TelemetryService` |
| `backend/trips/` | State machine, efficiency scaffold, repository, `TripService` |
| `backend/storage/` | SQLite `Database` + migrations (v3) |
| `backend/api/` | REST + WebSocket routes |
| `backend/health/` | Read-only DTC explanations, trends, maintenance |
| `backend/voice/` | Deterministic intent router, ~15s context, briefing, local-or-bearer auth |
| `frontend/` | React PWA dashboard, hooks, IndexedDB replica + glance, Voice lab |
| `deploy/` | Hardened systemd unit examples + env placeholders |
| `tests/` | pytest coverage for simulator, OBD stub, allowlist, trips, sync, health, voice, API |

App wiring: `backend/main.py` → `create_app()` constructs DB, `TripService`, `HealthService`, `VoiceService`, `TelemetryService(build_provider(), on_sample=trips+health)`.

## TelemetryProvider swap (simulator ↔ OBD)

Contract (`backend/telemetry/provider.py`):

- `connect()` / `disconnect()`
- `discover_capabilities() → dict` (allowlist ∩ supported; unsupported → unavailable)
- `read() → TelemetrySample` (allowlisted PIDs only)
- `capabilities() → dict` (sync snapshot; always `read_only: true`, `can_clear_codes: false`)
- `is_connected()`

Allowlist module: `backend/telemetry/allowlist.py` — Mode 01 live metrics + Mode 03 DTC read; forbidden clear/control modes.

**SIMULATOR (default):** `SimulatorProvider` (`source="simulator"`, `simulated=True`, scenarios via `/api/simulator/scenario`).

**OBD (stub today):** `ObdProvider` — same ABC; `is_connected()=False`; samples/capabilities report **adapter not connected**; no serial traffic. Sunday: wire python-OBD behind this class without changing trips/API.

`NullProvider` remains a disconnected placeholder. Injection: `create_app(provider=...)` or env factory.

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
- Production Pi sketch: hardened systemd units for uvicorn + optional static frontend; nginx preferred for single-origin proxy. Still **local-only**. See [security-and-power.md](./security-and-power.md) and [../deploy/README.md](../deploy/README.md).

## What is intentionally stubbed / gated

- Voice: **intent routing + text Voice lab done**; wake word, ASR, TTS, and iPhone PWA background audio remain open (audio feasibility gate).
- Maps / Spotify: encoded deep-link + open/Siri **stubs** (see [infotainment.md](./infotainment.md)); verified launches / OAuth PKCE later with owner approval; never fabricate map/police data.
- Trusted HTTPS CA: later phases.
- Real OBD hardware: unverified; in-tree stub only until Sunday. Health DTC demos remain simulator scenarios.
