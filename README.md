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
**Idle → Cruise → Disconnect → Recover** (plus Parked / Auto). Parked mode is never inferred from 0 mph alone.

Force a scenario from the UI buttons, or via API:

```bash
curl -X POST http://127.0.0.1:8000/api/simulator/scenario \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"disconnect"}'
```

Valid scenarios: `auto`, `parked`, `idle`, `cruise`, `disconnect`, `recover`.

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

**Security:** `0.0.0.0` and LAN CORS allow only localhost + private RFC1918 origins. Keep this on your **trusted local network only**. Do not port-forward, put it on a public IP, or leave it reachable from the open internet. Phase 1 has no auth.

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
  frontend/     React + TypeScript PWA (manifest, icons, IndexedDB glance cache)
  backend/      FastAPI (telemetry, trips, health, voice, storage, api)
  simulator/    Interchangeable TelemetryProvider + demo scenarios
  deploy/       Pi deploy placeholders (Phase 2+)
  tests/
  docs/
```

## Phase 1 scope / limitations
- Simulated drive cycle only; not real vehicle data.
- Trip / health / voice / maintenance endpoints are stubs (parked UI shows placeholder history).
- SQLite facade exists (schema v0); full trip persistence is Phase 3. IndexedDB stores last sample + connection glance for offline UI.
- No Pi deploy, trusted HTTPS, OBD, wake word, Spotify, or maps yet.
- Google Fonts require network; UI falls back to local fonts offline.

## Safety
Read-only diagnostics by design. No clear-DTC, ECU, actuator, or steering/brake/throttle commands. Factory instruments remain authoritative.
