# AccordOS — project context

Practical overview for Sunday Pi work (**Nov 29, 2026**). Soft gate tonight: **Tue Nov 24, 2026 (America/New_York)**.

**Main tip:** `11fc4ae` — merge of [PR #6](https://github.com/trentderosa/accordos/pull/6) (OBD provider interface + allowlist stub). No open feature PRs.

## What’s on main

| Area | On `main` now |
|---|---|
| Telemetry | `TelemetryProvider` + **SimulatorProvider** (default) + **ObdProvider** stub (`adapter not connected`) |
| Switch | `ACCORDOS_PROVIDER=SIMULATOR\|OBD` via factory; PID allowlist module |
| Trips | SQLite journal, recovery, sync + IndexedDB replica, export/restore |
| Health | Read-only diagnostics / trends / maintenance; never clears codes |
| Voice | Deterministic intent router + Voice lab; **no** wake-word / ASR / TTS yet |
| Infotainment | Waze + Apple Maps deep links; Spotify open/Siri stub (no secrets) |
| Deploy | Hardened `deploy/accordos-backend.service` + optional frontend unit |
| Tests | `pytest -q` → **105 passed** (post–PR #6) |

UI is a quiet Tesla-like cluster (deep charcoal, large white gauges, soft blue). Chrome shows **SIMULATED** or **OBD** from provider truth. Same-LAN iPhone path exists (`0.0.0.0` Vite + uvicorn); owner still needs a real-device try.

## Open items

| Item | Status |
|---|---|
| **iPhone try** | LAN PWA path ready on Mac; confirm Safari / Add to Home Screen before Sunday if possible |
| **microSD Sunday** | Reader at school apartment; inspect + backup before any reimage (**Gate G1**) |
| **Real OBD** | Stub only on main; python-OBD + compatible adapter **unverified** — wire only if present and G2 cleared |
| **Wake word** | Intent routing shipped; audio feasibility / ASR / TTS still open |
| **HTTPS** | Deferred until Pi boots cleanly on trusted LAN; no public exposure |

## Doc index

| Doc | Purpose |
|---|---|
| [project-context.md](./project-context.md) | This page — goals, main tip, open items |
| [sunday-pi-setup.md](./sunday-pi-setup.md) | **Nov 29** step-by-step + current software state + stop-and-ask gates |
| [runbook-mac.md](./runbook-mac.md) | Mac simulator run (backend, frontend, LAN iPhone) |
| [architecture.md](./architecture.md) | Data flow, modules, SIMULATOR ↔ OBD swap |
| [obd-provider.md](./obd-provider.md) | Provider contract, allowlist, OBD stub, env switch |
| [api.md](./api.md) | Endpoints that exist now |
| [security-and-power.md](./security-and-power.md) | Local-only network, ignition power, no ECU writes |
| [trip-intelligence.md](./trip-intelligence.md) | Trip state machine, SQLite journal, demo |
| [voice-intents.md](./voice-intents.md) | Deterministic routing, briefing, Voice lab, audio gate |
| [infotainment.md](./infotainment.md) | Maps deep links, Spotify stub, OAuth PKCE path (not wired) |
| [../deploy/README.md](../deploy/README.md) | Systemd units + env placeholders (no secrets) |
| [../README.md](../README.md) | Repo entry + quick start |

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
| Vehicle data | `TelemetryProvider` → **SimulatorProvider** today; **ObdProvider** stub until real adapter |
| Persistence | SQLite on host (`data/accordos.db`); phone IndexedDB last-sample cache |
| Deploy target | Raspberry Pi OS Lite + systemd (Phase 2; sketches in `deploy/`) |

Data flow:

`TelemetryProvider (SIMULATOR | OBD stub) → TelemetryService → TripService → SQLite`  
`→ FastAPI REST/WS → React PWA → IndexedDB glance`

Provider swap via `ACCORDOS_PROVIDER`; trip/API contracts stay the same.

## What’s next

| When | Focus |
|---|---|
| Through Sat Nov 28 | Optional Mac polish / iPhone LAN try; do **not** require Pi or car |
| **Sun Nov 29** | Hardware day — [sunday-pi-setup.md](./sunday-pi-setup.md). Inspect/backup microSD, boot verify, network, clone `main`, run backend (+ serve PWA). Wire python-OBD into `ObdProvider` only if a compatible adapter is present and authorized (read-only allowlist) |
| After Pi boots cleanly | Trusted local HTTPS, auth/pairing, real PID discovery behind allowlist, power plan |
| Later | Wake word / ASR / TTS (after audio gate); verified map launches under iOS gesture rules; Spotify PKCE only with owner approval |

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
