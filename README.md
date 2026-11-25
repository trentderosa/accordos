# AccordOS

Offline-first smart vehicle platform for a 2014 Honda Accord. Runs entirely on a MacBook with a **SIMULATED** telemetry provider — no vehicle, Pi, or OBD hardware required. **Trip intelligence** journals simulated drives to SQLite; **health core** explains read-only diagnostic codes and telemetry trends (never clears codes); **voice intents** route typed commands locally (no wake-word training, no paid LLM).

**Sunday (Nov 29) start here → [docs/sunday-pi-setup.md](docs/sunday-pi-setup.md)**  
(Context + gates: [docs/project-context.md](docs/project-context.md) · safety: [docs/security-and-power.md](docs/security-and-power.md))

## Doc index

| Doc | Purpose |
|---|---|
| [docs/project-context.md](docs/project-context.md) | Goals, architecture summary, what’s built / next, constraints |
| [docs/sunday-pi-setup.md](docs/sunday-pi-setup.md) | **Nov 29** step-by-step Pi day (backup, image, boot, network, run, OBD read-only, stop-and-ask gates) |
| [docs/runbook-mac.md](docs/runbook-mac.md) | Current Mac simulator run (backend, frontend, LAN iPhone) |
| [docs/architecture.md](docs/architecture.md) | Data flow, modules, simulator ↔ future OBD provider swap |
| [docs/api.md](docs/api.md) | Endpoints that exist now |
| [docs/security-and-power.md](docs/security-and-power.md) | Local-only network, ignition power, no ECU writes |
| [docs/trip-intelligence.md](docs/trip-intelligence.md) | Trip state machine, SQLite journal, demo script |
| [docs/voice-intents.md](docs/voice-intents.md) | Deterministic voice routing, briefing, Voice lab, audio gate |
| [deploy/README.md](deploy/README.md) | systemd / env placeholders for Pi (no secrets) |

OBD adapter compatibility is **unverified**. These docs are not a shopping list.

## Quick start (macOS)

Full detail: [docs/runbook-mac.md](docs/runbook-mac.md).

### Prerequisites
- Python 3.9+
- Node.js 20+ (22 recommended)

### 1. Backend

```bash
cd accordos
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
# from repo root so `backend` and `simulator` import cleanly
# Default host 0.0.0.0 = reachable on your LAN (see security note below)
uvicorn backend.main:app --app-dir . --host 0.0.0.0 --port 8000
```

API docs: http://127.0.0.1:8000/docs  
WebSocket: `ws://127.0.0.1:8000/ws/telemetry`

Loopback-only (no LAN): `ACCORDOS_HOST=127.0.0.1 uvicorn backend.main:app --app-dir . --host 127.0.0.1 --port 8000`

### 2. Frontend (separate terminal)

```bash
cd accordos/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite listens on `0.0.0.0:5173` and proxies `/api` and `/ws` to the backend on the Mac.

You should see a dark charcoal cluster labeled **SIMULATED**, with demo scenario controls:
**Idle → Cruise → Disconnect → Recover** (plus Parked / Auto) and health demos
**Healthy / P0420 / Misfire / Overheat / Low V**. Parked mode is never inferred from 0 mph alone.
In parked mode, open **Vehicle health** for codes, trends, and maintenance reminders, and use **Voice lab** to type intent commands.

Force a scenario from the UI buttons, or via API:

```bash
curl -X POST http://127.0.0.1:8000/api/simulator/scenario \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"check_engine"}'
```

Valid scenarios: `auto`, `parked`, `idle`, `cruise`, `disconnect`, `recover`,
`healthy`, `check_engine`, `misfire`, `overheat`, `low_voltage`.

## Try on iPhone (same Wi‑Fi / LAN)

`127.0.0.1` on the phone means the phone itself — it will **not** reach your Mac. Use the Mac’s LAN IP instead.

1. Mac and iPhone on the **same Wi‑Fi** (not guest/client isolation if your router has it).
2. Start backend + frontend as above (`0.0.0.0` hosts).
3. On the Mac, find the LAN address:

```bash
ipconfig getifaddr en0
# or: ipconfig getifaddr en1
```

4. On iPhone Safari open: `http://<mac-lan-ip>:5173`  
   Example: `http://192.168.1.42:5173`
5. Confirm the cluster streams **SIMULATED** data and scenario buttons work.
6. Optional install: Share → **Add to Home Screen** (Safari). Theme/icons come from the PWA manifest.  
   Note: full trusted HTTPS for standalone PWA features is Phase 2; HTTP on LAN is fine for this Phase 1 glance.
7. Offline glance: after a live session, kill the backend — gauges should show the **last cached** reading with an honest **Cached glance** banner (IndexedDB on the phone).

**Security:** `0.0.0.0` and LAN CORS allow only localhost + private RFC1918 origins. Keep this on your **trusted local network only**. Do not port-forward, put it on a public IP, or leave it reachable from the open internet. Phase 1 has no auth. Details: [docs/security-and-power.md](docs/security-and-power.md).

macOS may prompt to allow incoming connections for Node/Python the first time — allow for local network.

## Tests

```bash
cd accordos
source .venv/bin/activate
pytest -q
```

### Production-ish frontend build

```bash
cd frontend && npm run build && npm run preview
```

Preview also binds `0.0.0.0:4173` with the same `/api` + `/ws` proxy.

## Layout

```
accordos/
  frontend/     React + TypeScript PWA (manifest, icons, IndexedDB glance + trip replica)
  backend/      FastAPI (telemetry, trips, health, voice, storage, api)
  simulator/    Interchangeable TelemetryProvider + demo scenarios
  deploy/       Pi systemd / env sketches (Phase 2+)
  tests/
  docs/         Project context, Sunday Pi, runbooks, API, security
```

## Trip intelligence (simulator)

Trips start from debounced engine-running evidence (RPM + communication), never from speed alone. Summaries (distance, duration, avg/max speed, idle time) land in SQLite; fuel and efficiency scores appear only when inputs/confidence allow.

**Demo:** Cruise (or Auto) → optional Idle / Disconnect / Recover → Parked (~3s) → **Recent trips** syncs via `GET /api/sync`; kill backend to confirm offline replica; Export JSON/CSV under the list. Details: [docs/trip-intelligence.md](docs/trip-intelligence.md).

Default DB: `data/accordos.db` (`ACCORDOS_DB` to override; `:memory:` for ephemeral).

## Scope / limitations
- Simulated drive cycle only; not real vehicle data.
- Trip journal, health core, and deterministic voice intents are live on the simulator. Wake word / ASR / TTS are not.
- **Audio feasibility gate is open:** iPhone PWA TTS and background playback are unproven — Voice lab is text-first. See [docs/voice-intents.md](docs/voice-intents.md).
- SQLite schema v3 (trips + sync revisions + diagnostic/trend/maintenance tables). IndexedDB stores glance cache and a synced trip replica; JSON/CSV export/restore from the PWA.
- Health explains codes with vetted static reference data; codes ≠ diagnoses; AccordOS never clears DTCs.
- No Pi deploy yet beyond sketches; trusted HTTPS, OBD, wake word, Spotify API, and verified map launches are later. See [docs/sunday-pi-setup.md](docs/sunday-pi-setup.md) and [docs/runbook-mac.md](docs/runbook-mac.md).
- Google Fonts require network; UI falls back to local fonts offline.
- OBD/adapter untested — do not buy hardware from this README.

## Safety
Read-only diagnostics by design. No clear-DTC, ECU, actuator, or steering/brake/throttle commands. Factory instruments remain authoritative. Ignition-switched power in the car — see [docs/security-and-power.md](docs/security-and-power.md).
