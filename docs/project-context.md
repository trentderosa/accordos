# AccordOS — project context

Practical overview for anyone picking up the repo before Sunday Pi work (Nov 29, 2026).

## Goals

- Removable, **offline-first** smart vehicle platform for a base **2014 Honda Accord**.
- Tesla-inspired instrument cluster + parked trip/history UI, served as an installable **PWA on iPhone**.
- Computer is the owner's **Raspberry Pi 3 Model B V1.2** — the MacBook is for development only and must never be required in the car.
- Preserve factory screen, stereo, and electronics. **No drilling, cutting wires, or permanent mods.**
- Core telemetry, trip history, and (later) local voice must work **without cloud or public internet**.

## Architecture (short)

| Layer | Choice now |
|---|---|
| Frontend | React + TypeScript PWA (Vite, manifest, service worker, IndexedDB glance) |
| Backend | Python FastAPI, REST + WebSocket telemetry |
| Vehicle data | `TelemetryProvider` interface → **SimulatorProvider** today; future read-only OBD |
| Persistence | SQLite on host (`data/accordos.db`); phone IndexedDB last-sample cache |
| Deploy target | Raspberry Pi OS Lite + systemd (Phase 2; sketches in `deploy/`) |

Data flow today:

`SimulatorProvider → TelemetryService → TripService → SQLite`  
`→ FastAPI REST/WS → React PWA → IndexedDB glance`

Future OBD swap replaces only the provider; trip/API contracts stay the same. Details: [architecture.md](./architecture.md).

## What’s built (as of main @ trip-intelligence)

- Scaffolded monorepo: `frontend/`, `backend/`, `simulator/`, `tests/`, `deploy/`, `docs/`.
- Live **SIMULATED** dashboard (driving/parked), connection/stale/cached indicators, demo scenarios.
- Same-LAN iPhone testing via `0.0.0.0` Vite + uvicorn (trusted LAN only).
- **Trip intelligence (simulator):** state machine, SQLite journal, recovery after abrupt stop, `GET /api/trips`, sync scaffold.
- Health / voice / maintenance **stubs** (read-only messaging; no vehicle commands).
- Tests: `pytest -q` for simulator, telemetry, trips, API.

See [trip-intelligence.md](./trip-intelligence.md) and [api.md](./api.md).

## What’s next

| When | Focus |
|---|---|
| Through Sat Nov 28 | Finish Mac/simulator polish; do **not** require Pi or car. |
| **Sun Nov 29** | Hardware day — follow [sunday-pi-setup.md](./sunday-pi-setup.md). Inspect/backup microSD, boot verify, network, clone, run backend (+ serve PWA). Optional **read-only** OBD only if a compatible adapter is present and authorized. |
| After Pi boots cleanly | Trusted local HTTPS, auth/pairing, real PID discovery, power plan. |
| Later phases | Full phone↔Pi sync polish, voice, health alerts, maps/Spotify deep links. |

## Constraints (non-negotiable)

- **No ECU writes:** no clear-DTC, coding, flashing, actuator, steering/brake/throttle commands.
- **No public internet exposure** for the API or PWA host.
- **Ignition-switched power** for the Pi — do not leave it on always-live OBD power indefinitely.
- Factory instruments remain authoritative.
- OBD adapter compatibility and real telemetry are **unverified**. Do not buy hardware from this doc; confirm before purchase.
- Pi 3 B has limited RAM/CPU — keep dependencies lean.
- Stop at phase gates; ask before paid APIs, native apps, architecture changes, or vehicle installs.

## Hardware status (Nov 24, 2026)

- Pi 3 Model B V1.2, SanDisk 16 GB microSD, power + HDMI cables available.
- Steady red power LED observed; **successful boot not yet verified**.
- Vehicle OBD-II port located; **adapter + live telemetry unverified**.
- microSD card reader at school apartment — available Sunday.

## Sunday start here

1. [sunday-pi-setup.md](./sunday-pi-setup.md) — step-by-step with stop-and-ask gates.  
2. [security-and-power.md](./security-and-power.md) — before any vehicle power or OBD plug-in.  
3. [deploy/README.md](../deploy/README.md) — env vars + systemd sketches (no secrets).  
4. [runbook-mac.md](./runbook-mac.md) — if you need to compare against the Mac simulator.
