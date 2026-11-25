# Mac runbook — simulator (current)

Reproduce the Phase 1 / trip-intelligence stack on macOS. No Pi, car, or OBD required.

## Prerequisites

- Python **3.9+**
- Node.js **20+** (22 recommended)
- Same Wi‑Fi as iPhone if testing on device (not guest/client-isolation)

## 1. Backend

```bash
cd accordos
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Default host 0.0.0.0 = reachable on LAN (trusted network only)
uvicorn backend.main:app --app-dir . --host 0.0.0.0 --port 8000
```

Or:

```bash
python -m backend.main
```

| Check | URL |
|---|---|
| Root | http://127.0.0.1:8000/ |
| OpenAPI | http://127.0.0.1:8000/docs |
| Status | http://127.0.0.1:8000/api/status |
| WS | `ws://127.0.0.1:8000/ws/telemetry` |

Loopback-only:

```bash
ACCORDOS_HOST=127.0.0.1 uvicorn backend.main:app --app-dir . --host 127.0.0.1 --port 8000
```

### Env vars

| Variable | Default | Meaning |
|---|---|---|
| `ACCORDOS_HOST` | `0.0.0.0` | Bind address (`127.0.0.1` = no LAN) |
| `ACCORDOS_PORT` | `8000` | HTTP/WS port |
| `ACCORDOS_DB` | `data/accordos.db` | SQLite path; use `:memory:` for ephemeral |

No secrets required for simulator mode. Do not commit `.env` files with credentials.

## 2. Frontend

Separate terminal:

```bash
cd accordos/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173  

Vite binds `0.0.0.0:5173` and proxies `/api` + `/ws` to `127.0.0.1:8000`.

You should see a dark charcoal cluster labeled **SIMULATED**, with scenario controls: **Idle → Cruise → Disconnect → Recover** (plus Parked / Auto). Parked mode is never inferred from 0 mph alone.

### Force a scenario via API

```bash
curl -X POST http://127.0.0.1:8000/api/simulator/scenario \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"disconnect"}'
```

Valid: `auto`, `parked`, `idle`, `cruise`, `disconnect`, `recover`.

## 3. iPhone on the same LAN

`127.0.0.1` on the phone is the phone — use the Mac’s LAN IP.

```bash
ipconfig getifaddr en0
# or: ipconfig getifaddr en1
```

1. Start backend + frontend as above.
2. iPhone Safari: `http://<mac-lan-ip>:5173`
3. Confirm **SIMULATED** stream + scenario buttons.
4. Optional: Share → **Add to Home Screen**. Trusted HTTPS for full standalone PWA features is still Phase 2.
5. Offline glance: after a live session, stop the backend — gauges should show last cached sample + **Cached glance** banner.

macOS may prompt to allow incoming Node/Python connections — allow for local network.

**Security:** LAN CORS allows localhost + private RFC1918 origins only. No port-forward. Phase 1 has **no auth**.

## 4. Demo a full simulated trip

1. Open the dashboard.
2. **Cruise** (or Auto) — trip starts after engine-on debounce; distance accumulates.
3. Optional **Idle** — speed 0, RPM up; trip stays active.
4. Optional **Disconnect** / **Recover** — trip stays open across signal loss.
5. **Parked** ~3s — trip finalizes to SQLite.
6. Parked **Recent trips**, or:

```bash
curl -s http://127.0.0.1:8000/api/trips | python3 -m json.tool
```

Details: [trip-intelligence.md](./trip-intelligence.md).

## 5. Tests and production-ish preview

```bash
cd accordos
source .venv/bin/activate
pytest -q
```

```bash
cd frontend && npm run build && npm run preview
```

Preview: `0.0.0.0:4173` with the same `/api` + `/ws` proxy.

## Troubleshooting

| Symptom | Check |
|---|---|
| Phone blank / can’t connect | Same Wi‑Fi? Using LAN IP not 127.0.0.1? Firewall allow? |
| API 404 from Vite | Backend up on :8000? Proxy in `vite.config.ts` |
| Empty trips | Finalize via Parked debounce; confirm `data/accordos.db` |
| Port in use | Change `ACCORDOS_PORT` / Vite port; kill old uvicorn |
| Import errors | Run uvicorn from **repo root** with `--app-dir .` |

## Out of scope on Mac

Pi imaging, real OBD, trusted HTTPS CA install, systemd, vehicle power. Those are Sunday+: [sunday-pi-setup.md](./sunday-pi-setup.md).
