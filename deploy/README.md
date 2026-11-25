# Deploy (Raspberry Pi)

Phase 2+ sketches. **Do not enable systemd until** the backend runs cleanly by hand — see [docs/sunday-pi-setup.md](../docs/sunday-pi-setup.md).

No secrets belong in this folder. Use environment files outside Git (e.g. `/etc/accordos.env` with mode `600`).

## Environment placeholders

Create `/etc/accordos.env` (example — adjust user/paths):

```bash
# /etc/accordos.env — NOT committed to Git
ACCORDOS_HOST=0.0.0.0
ACCORDOS_PORT=8000
ACCORDOS_DB=/home/pi/accordos/data/accordos.db
# Future:
# ACCORDOS_PROVIDER=simulator   # or obd when implemented
# ACCORDOS_CORS_EXTRA=
```

| Variable | Placeholder meaning |
|---|---|
| `ACCORDOS_HOST` | Bind address (`0.0.0.0` LAN; prefer firewall still) |
| `ACCORDOS_PORT` | Backend port (default `8000`) |
| `ACCORDOS_DB` | Absolute path to SQLite file |
| `ACCORDOS_PROVIDER` | *(future)* `simulator` \| `obd` |

Never put Wi‑Fi passwords, SSH keys, or API client secrets in the repo or in unit files checked into Git.

## systemd unit sketch — backend

Save as `/etc/systemd/system/accordos-backend.service` after manual success:

```ini
[Unit]
Description=AccordOS backend (FastAPI / uvicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/accordos
EnvironmentFile=-/etc/accordos.env
ExecStart=/home/pi/accordos/.venv/bin/uvicorn backend.main:app --app-dir /home/pi/accordos --host ${ACCORDOS_HOST} --port ${ACCORDOS_PORT}
Restart=on-failure
RestartSec=5
# Harden lightly — expand later
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable only when ready:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now accordos-backend.service
sudo systemctl status accordos-backend.service
journalctl -u accordos-backend -f
```

Replace `User=` / paths with the actual Linux username and clone location.

## Serving the PWA (sketch)

Options:

1. **Short-term:** `npm run preview` under a second unit or `tmux` (OK for Sunday verify).
2. **Preferred later:** build `frontend/dist`, serve with **nginx** (or Caddy) on `:443` / `:80`, reverse-proxy `/api` and `/ws` to uvicorn.

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
```

Keep `data/accordos.db` off the destructive path; never `git clean -fdx` without confirming DB backup.

## Security reminders

- Local / trusted network only — see [docs/security-and-power.md](../docs/security-and-power.md).
- No public port-forward.
- Read-only vehicle interface forever.
