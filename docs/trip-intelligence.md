# AccordOS trip intelligence (simulator Phase 3 core)

Offline-first trip journal on the Mac simulator. No vehicle hardware or Pi required.

Related: [project-context.md](./project-context.md) · [api.md](./api.md) · [runbook-mac.md](./runbook-mac.md) · Sunday Pi: [sunday-pi-setup.md](./sunday-pi-setup.md)

## What landed

- **State machine:** `idle → starting → active → ending → finalized` (or `recovered` after interruption).
- **Engine-running evidence:** RPM + communication quality, with debounce. A trip **never** ends only because speed is 0.
- **SQLite:** schema v1 migrations (`trips`, `trip_samples`, `trip_checkpoints`); continuous samples + periodic checkpoints.
- **Recovery:** incomplete open rows are marked `recovered` + `incomplete` after process/“power” loss.
- **Summaries:** start/end, duration, distance (integrated speed), avg/max speed, idle time; fuel estimates only when inputs allow; otherwise honest `unavailable` / `insufficient`.
- **Efficiency scaffold:** proposed weights (accel 25 / decel 25 / fuel 25 / engine 15 / idle 10). Score withheld with explanation when confidence is low — not a safety rating.
- **API:** `GET /api/trips` and `GET /api/trips/{id}` read SQLite (not placeholders).
- **UI:** parked **Recent trips** polls the real API; keeps SIMULATED labeling.

## Demo a full simulated trip (end-to-end)

```bash
cd accordos
source .venv/bin/activate
uvicorn backend.main:app --app-dir . --host 127.0.0.1 --port 8000
# other terminal:
cd frontend && npm run dev
```

1. Open http://127.0.0.1:5173
2. Tap **Cruise** (or leave **Auto**) — engine-on debounce starts a trip; distance accumulates.
3. Optionally tap **Idle** — speed 0 with RPM still running; trip stays active.
4. Optionally **Disconnect** then **Recover** — trip stays open across signal loss.
5. Tap **Parked** and wait ~3s (engine-off debounce) — trip finalizes to SQLite.
6. Parked **Recent trips** lists the drive (distance, duration; efficiency may show “withheld”).

API check:

```bash
curl -s http://127.0.0.1:8000/api/trips | python3 -m json.tool
```

DB file (default): `accordos/data/accordos.db` (override with `ACCORDOS_DB`).

## Tests

```bash
pytest -q
```

Covers synthetic trips, zero-speed idle, disconnect, abrupt shutdown recovery, duplicate sample timestamps, and REST from SQLite.

## Out of scope (this slice)

Pi deploy, voice, maps, Spotify, clearing DTCs, phone↔Pi incremental sync polish beyond the sync scaffold.
