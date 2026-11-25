# AccordOS

Offline-first smart vehicle platform for a 2014 Honda Accord. **Phase 1** runs entirely on a MacBook with a **SIMULATED** telemetry provider — no vehicle, Pi, or OBD hardware required.

## Quick start (macOS)

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
uvicorn backend.main:app --app-dir . --host 127.0.0.1 --port 8000
```

API docs: http://127.0.0.1:8000/docs  
WebSocket: `ws://127.0.0.1:8000/ws/telemetry`

### 2. Frontend (separate terminal)

```bash
cd accordos/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — Vite proxies `/api` and `/ws` to the backend.

You should see a dark dashboard labeled **SIMULATED**, cycling through parked → driving → idle. Disconnect the backend to verify the connection indicator.

### Tests

```bash
cd accordos
source .venv/bin/activate
pytest -q
```

### Production-ish frontend build

```bash
cd frontend && npm run build && npm run preview
```

## Layout

```
accordos/
  frontend/     React + TypeScript PWA
  backend/      FastAPI (telemetry, trips, health, voice, storage, api)
  simulator/    Interchangeable TelemetryProvider
  deploy/       Pi deploy placeholders (Phase 2+)
  tests/
  docs/
```

## Phase 1 scope / limitations
- Simulated drive cycle only; not real vehicle data.
- Trip / health / voice / maintenance endpoints are stubs.
- SQLite facade exists (schema v0); persistence is Phase 3.
- No Pi deploy, HTTPS, OBD, wake word, Spotify, or maps yet.
- Google Fonts require network; UI falls back to local fonts offline.

## Safety
Read-only diagnostics by design. No clear-DTC, ECU, actuator, or steering/brake/throttle commands. Factory instruments remain authoritative.
