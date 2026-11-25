# Deploy (Raspberry Pi)

Phase 2 sketches. **Do not enable systemd until** the backend runs cleanly by hand — see [docs/sunday-pi-setup.md](../docs/sunday-pi-setup.md).

No secrets belong in this folder. Use environment files outside Git (e.g. `/etc/accordos.env` with mode `600`).

## Unit files in this folder

| File | Role |
|---|---|
| [accordos-backend.service](./accordos-backend.service) | uvicorn backend with hardening flags |
| [accordos-frontend.service](./accordos-frontend.service) | **Optional** static `frontend/dist` serve (no `/api` proxy) |

Copy after manual success:

```bash
sudo cp deploy/accordos-backend.service /etc/systemd/system/
# optional:
sudo cp deploy/accordos-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now accordos-backend.service
sudo systemctl status accordos-backend.service
journalctl -u accordos-backend -f
```

Replace `User=` / paths with the actual Linux username and clone location. If you later attach a USB OBD adapter, you may need to relax `PrivateDevices=true` and add a `DeviceAllow=` — leave closed until then.

## Environment placeholders

Create `/etc/accordos.env` (example — adjust user/paths):

```bash
# /etc/accordos.env — NOT committed to Git
ACCORDOS_HOST=0.0.0.0
ACCORDOS_PORT=8000
ACCORDOS_DB=/home/pi/accordos/data/accordos.db
ACCORDOS_PROVIDER=SIMULATOR
# Switch only when ready to exercise the OBD stub / Sunday wiring:
# ACCORDOS_PROVIDER=OBD
# Optional voice bearer for non-loopback clients:
# ACCORDOS_VOICE_TOKEN=
ACCORDOS_FRONTEND_PORT=4173
```

| Variable | Meaning |
|---|---|
| `ACCORDOS_HOST` | Bind address (`0.0.0.0` LAN; prefer firewall still) |
| `ACCORDOS_PORT` | Backend port (default `8000`) |
| `ACCORDOS_DB` | Absolute path to SQLite file |
| `ACCORDOS_PROVIDER` | `SIMULATOR` (default) or `OBD` (stub until python-OBD) |
| `ACCORDOS_VOICE_TOKEN` | Optional bearer for non-local voice POSTs |
| `ACCORDOS_FRONTEND_PORT` | Port for optional static frontend unit |

Never put Wi‑Fi passwords, SSH keys, or API client secrets in the repo or in unit files checked into Git.

## Provider switch

- **SIMULATOR** — default Mac/Pi path; full demo scenarios.
- **OBD** — `ObdProvider` stub: read-only allowlist, honest `adapter not connected` until Sunday python-OBD wiring. No vehicle writes.

See [docs/obd-provider.md](../docs/obd-provider.md).

## Serving the PWA

Options:

1. **Short-term:** `npm run preview` under tmux, or enable `accordos-frontend.service` after `npm run build` (static only — phone must call backend `:8000` for API/WS, or use Vite proxy on Mac).
2. **Preferred:** build `frontend/dist`, serve with **nginx** (or Caddy) on `:80`, reverse-proxy `/api` and `/ws` to uvicorn.

nginx location sketch (HTTP LAN only until trusted certs exist):

```nginx
server {
    listen 80;
    server_name accordos.local;  # or Pi IP

    root /home/pi/accordos/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Trusted HTTPS for installable PWA secure-context features is a follow-up — do not disable certificate validation.

## Rollback / updates (outline)

```bash
cd /home/pi/accordos
git fetch origin
git log HEAD..origin/main --oneline   # review before pulling
git pull origin main
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build
sudo systemctl restart accordos-backend
# sudo systemctl restart accordos-frontend   # if enabled
```

Keep `data/accordos.db` off the destructive path; never `git clean -fdx` without confirming DB backup.

## Security reminders

- Local / trusted network only — see [docs/security-and-power.md](../docs/security-and-power.md).
- No public port-forward.
- Read-only vehicle interface forever (`can_clear_codes: false`).
