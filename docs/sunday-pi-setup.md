# Sunday Pi setup — Nov 29, 2026

Step-by-step for the first Raspberry Pi day. Goal: inspect/backup the microSD, boot Raspberry Pi OS Lite if authorized, get networking, run AccordOS backend (simulator still OK), serve the PWA on the local network, and only then consider **read-only** OBD checks.

**Read first:** [security-and-power.md](./security-and-power.md)  
**Mac reference:** [runbook-mac.md](./runbook-mac.md)  
**Deploy sketches:** [../deploy/README.md](../deploy/README.md)

Hardware assumed available: Pi 3 Model B V1.2, 16 GB SanDisk microSD, power cable, HDMI cable, microSD reader (at school apartment). **OBD adapter is unverified** — skip OBD sections if you do not have a Linux-compatible adapter yet. This doc does **not** authorize buying hardware.

---

## Stop-and-ask gates

Stop and ask the owner (or pause the session) before:

| Gate | Why |
|---|---|
| **G1 — Wipe / reimage microSD** | Destroys existing card contents. Backup first; need explicit OK to image. |
| **G2 — Connect to vehicle power or OBD port** | Electrical + bus risk. Parked only; ignition-switched plan must be clear. |
| **G3 — Any write/clear/control OBD command** | Forbidden. AccordOS is read-only by design. |
| **G4 — Expose Pi beyond trusted LAN** | No port-forward, no public IP, no “temporary” tunnel. |
| **G5 — Permanent mounting / cutting / splicing** | Removable install only. |
| **G6 — Change architecture (native app, cloud, paid API)** | Out of Phase 2 scope without approval. |

If unsure, **stop**. Prefer documenting the question over guessing.

---

## 0. Before you leave / pack checklist

- [ ] Pi 3 B, microSD, reader, power supply, HDMI + display/TV or headless plan
- [ ] Ethernet cable (recommended for first boot) or known Wi‑Fi SSID/password
- [ ] Laptop with SSH client and this repo cloned (or GitHub access to clone on Pi)
- [ ] USB keyboard (if first boot needs local login)
- [ ] Notepad for hostname, LAN IP, and “what we did”
- [ ] Do **not** bring unverified adapters into the car until G2 is cleared

---

## 1. Inspect and back up the microSD

1. Insert the SanDisk 16 GB card into the reader on a Mac.
2. Note partitions / volumes that appear (Disk Utility or `diskutil list`).
3. **Backup before any write:**
   - Copy any visible files to a dated folder (e.g. `~/Desktop/pi-sd-backup-2026-11-29/`).
   - Optionally image the whole card (slow, safest):

```bash
# Identify the disk carefully — wrong disk = data loss
diskutil list
# Example only — replace rdiskN after you confirm:
# sudo dd if=/dev/rdiskN of=~/Desktop/pi-sd-backup-2026-11-29.img bs=4m
```

4. Record what you found: blank? old Raspberry Pi OS? other project?

**→ Gate G1:** Do not reimage until backup is done and owner authorizes wipe.

---

## 2. Image Raspberry Pi OS Lite (only if authorized)

Preferred: **Raspberry Pi OS Lite** (64-bit if supported on Pi 3; otherwise 32-bit Lite) via Raspberry Pi Imager.

In Imager, set **before writing**:

- Hostname: e.g. `accordos`
- Enable SSH (password or better: public key)
- Username/password (strong; not `raspberry`/`raspberry`)
- Wi‑Fi country + credentials **or** plan to use Ethernet first
- Locale / timezone: America/New_York

Write the image, eject safely, insert into Pi.

**If owner declines reimage:** boot existing OS if present; document version with `cat /etc/os-release` after login; adapt later steps.

---

## 3. First boot verify

1. Connect HDMI + keyboard (or rely on SSH if Imager preconfigured).
2. Power with a known-good 5 V supply (desk PSU first — **not** the car yet).
3. Confirm boot: green ACT LED activity, login prompt or SSH reachable.
4. Login and run:

```bash
uname -a
cat /etc/os-release
free -h
df -h
vcgencmd measure_temp   # if available
hostname -I
```

5. Note RAM (~1 GB on Pi 3 B), free disk, temperature at idle.

**Stop if:** no boot, constant red LED only with no ACT, or SD errors. Re-seat card / recheck image before vehicle work.

---

## 4. Network

1. Prefer Ethernet for day-one stability.
2. Confirm LAN IP: `hostname -I`
3. From Mac on same network:

```bash
ping -c 3 <pi-ip>
ssh <user>@<pi-ip>
```

4. Optional Wi‑Fi later; test iPhone can reach the Pi on the **same SSID** (avoid guest/client-isolation SSIDs).
5. Do **not** enable UPnP, ngrok, or port-forward. See [security-and-power.md](./security-and-power.md).

---

## 5. Clone / pull AccordOS

On the Pi:

```bash
sudo apt update
sudo apt install -y git python3-venv python3-pip
# Node only if you will build the frontend on the Pi (optional day-one):
# sudo apt install -y nodejs npm   # or use NodeSource / nvm if apt node is too old

cd ~
git clone https://github.com/trentderosa/accordos.git
cd accordos
git pull origin main
git status
git log -1 --oneline
```

If the repo is already present: `git fetch && git pull origin main` only — do not force-reset without asking.

---

## 6. Python venv + backend

```bash
cd ~/accordos
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt

# Trusted LAN only — same pattern as Mac runbook
export ACCORDOS_HOST=0.0.0.0
export ACCORDOS_PORT=8000
# Optional: export ACCORDOS_DB=/home/<user>/accordos/data/accordos.db

uvicorn backend.main:app --app-dir . --host 0.0.0.0 --port 8000
```

Smoke check from Mac or phone browser on LAN:

- `http://<pi-ip>:8000/` → JSON root with `"note": "SIMULATED..."`
- `http://<pi-ip>:8000/docs` → OpenAPI
- `http://<pi-ip>:8000/api/status`

Leave the process in a `tmux`/`screen` session for the day, or install the systemd sketch from [../deploy/README.md](../deploy/README.md) **after** manual success.

---

## 7. Serve the PWA

Day-one options (pick one):

### A. Dev servers (fastest for verify)

If Node is installed on the Pi:

```bash
cd ~/accordos/frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

iPhone Safari: `http://<pi-ip>:5173` (same Wi‑Fi). Expect **SIMULATED** label.

### B. Production build + static host (lighter long-term)

```bash
cd ~/accordos/frontend
npm install
npm run build
# Serve `frontend/dist` with nginx or `python3 -m http.server` is NOT enough for /api proxy.
# Prefer nginx reverse-proxy to uvicorn (see deploy/README.md) or keep Vite preview:
npm run preview -- --host 0.0.0.0 --port 4173
```

**HTTPS / trusted cert:** not required to prove boot + API today; document as follow-up. Do not disable certificate checks as a workaround later.

---

## 8. First OBD checks (read-only only)

**Prerequisites:** Gate **G2** cleared; vehicle **parked**; factory instruments readable; adapter claimed Linux/ELM327-compatible (still **unverified** until this step).

1. Do **not** clear codes, reset ECUs, or send control commands — ever.
2. Desk-test adapter on Pi USB before the car if possible (`lsusb`, dmesg).
3. In car: ignition-switched accessory power for Pi (see security doc). Confirm outlet dies with ignition.
4. Plug adapter into OBD-II only when ready to observe; keep sessions short.
5. Use a **read-only** tool or a future AccordOS OBD provider with an explicit PID allowlist. Until that provider exists, any third-party CLI must be limited to **query/read**.
6. Record: which PIDs respond, which fail, bus errors, temperatures, voltages.
7. Unplug and power down cleanly when done.

**→ Gate G3:** If a tool offers “clear DTC”, “program”, or “actuator test” — refuse and disconnect.

AccordOS still runs on **SimulatorProvider** until an OBD provider is implemented and swapped in. Seeing simulated data on the Pi is success for day one.

---

## 9. Safety checklist (end of day)

- [ ] microSD backed up before any wipe
- [ ] Pi boots on desk power; IP + SSH noted
- [ ] AccordOS backend responds on LAN; UI shows **SIMULATED** unless live OBD provider is intentionally connected
- [ ] No public exposure / no port-forward
- [ ] No ECU writes attempted
- [ ] If car was used: parked only, ignition-switched power understood, wiring clear of pedals/steering/airbags
- [ ] Pi ventilated; not sealed in a hot closed compartment for long runs
- [ ] Secrets (Wi‑Fi, SSH keys, future API tokens) **not** committed to Git
- [ ] Notes written: OS version, IP, hostname, blockers, PID results (if any)

---

## Done / handoff notes template

```
Date: 2026-11-29
Hostname / IP:
OS image:
Backup location:
Backend: up?  PWA URL:
OBD: skipped / adapter model / PIDs seen:
Blockers / ask owner:
```

Next engineering steps after a clean Sunday: systemd unit enabled, local HTTPS plan, OBD provider behind `TelemetryProvider`, resource profiling on Pi 3 B.
