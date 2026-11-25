# Security and power

Hard rules for Mac LAN testing and Sunday Pi / vehicle work. Read before plugging anything into the Accord.

## Network — local only

- AccordOS is designed for a **trusted local network** (home LAN, or a future Pi access point).
- Dev servers bind `0.0.0.0` so a phone on the same Wi‑Fi can connect. That is **not** an invitation to expose the service.
- **Do not:** port-forward, put the Pi/Mac on a public IP, use a public reverse proxy, or leave the API on the open internet.
- CORS allows localhost and **RFC1918** private origins only. Most endpoints still have **no auth** — treat LAN access as full access.
- Exception: `POST /api/voice/command` is **local-or-bearer** (loopback free; non-local needs `ACCORDOS_VOICE_TOKEN`). Voice never executes shell or vehicle controls.
- Prefer SSH with keys over passwords; disable password SSH once keys work.
- Keep secrets (Wi‑Fi, tokens, future Spotify client secrets) **out of Git**. Deploy placeholders use env files that are not committed.
- Future: pairing/auth, firewall, origin validation, trusted local HTTPS for PWA secure-context features. Do not “fix” HTTPS with certificate bypass.

## Vehicle / OBD — read-only

- Diagnostics are **read-only by design**.
- **Never:** clear DTCs, reset ECUs, flash/code modules, run actuator tests, or send steering / braking / throttle / safety-critical CAN commands.
- Factory instruments and warnings remain **authoritative**. Absent codes ≠ “healthy.”
- OBD adapter compatibility with this Pi/Linux stack is **unverified**. Do not assume any adapter works; do not treat this doc as a buy list.
- Until an allowlisted OBD provider exists in-tree, any external OBD tool must be limited to query/read. If a UI offers clear/program — stop (Gate G3 in [sunday-pi-setup.md](./sunday-pi-setup.md)).

## Power — ignition switched

- Power the Pi from an **ignition-switched**, automotive-rated 12 V → USB supply once in the car.
- **Do not** run the Pi indefinitely from an always-live OBD port feed.
- Verify the accessory outlet (or chosen tap) **turns off with ignition** before relying on it.
- Plan for abrupt power loss: SQLite trip checkpoints already assume interrupt; still prefer clean shutdown / future hold-up hardware when approved.
- Desk-test on a known-good 5 V supply before first car power.

## Thermal and physical

- Ventilate the Pi; do not rely on a sealed hot console for cooling.
- Removable mounting only — no drilling, cutting, or permanent wiring mods.
- Keep cables clear of pedals, steering column, airbags, and controls.
- Microphone (later) outside a closed compartment if the Pi is tucked away.

## Privacy

- No cloud upload by default.
- Minimize retained location and voice data when those features arrive; provide delete/export later.
- Phone IndexedDB may be evicted by iOS — do not promise durable phone-only history without Pi sync + export.

## Quick checklist

- [ ] Trusted LAN only; no public exposure
- [ ] No ECU writes / clear-DTC
- [ ] Ignition-switched power plan understood
- [ ] Parked for any first OBD experiment
- [ ] Factory warnings trusted over the app
- [ ] No secrets in the repo
