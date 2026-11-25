# AccordOS API (as implemented)

Base URL (Mac/Pi local): `http://127.0.0.1:8000` or `http://<lan-ip>:8000`  
Interactive docs: `/docs`  
API version reported in status/root: **0.3.0** (phase field may say `3` for trip-intelligence core; Pi hardware is still Phase 2).

All telemetry today is **SIMULATED** unless a future OBD provider is injected. No authentication yet — trusted LAN only.

## Root

### `GET /`

```json
{
  "app": "AccordOS",
  "phase": 3,
  "phase_note": "Trip intelligence on simulator (Phase 3 core); Pi hardware still Phase 2",
  "api_version": "0.3.0",
  "docs": "/docs",
  "ws": "/ws/telemetry",
  "note": "SIMULATED telemetry — not a real vehicle",
  "lan": "..."
}
```

---

## Capabilities & status

### `GET /api/capabilities`

Provider-declared metrics and constraints (`read_only`, simulator flags). Shape comes from `TelemetryProvider.capabilities()`.

### `GET /api/status`

```json
{
  "app": "AccordOS",
  "phase": 3,
  "api_version": "0.3.0",
  "connection": { "...": "from TelemetryService" },
  "trip": {
    "current": { "...": "in-progress trip or null" },
    "schema_version": 1
  }
}
```

---

## Telemetry

### `GET /api/telemetry/latest`

Latest `TelemetrySample` as JSON, plus `label`: `"SIMULATED"` or `"LIVE"`.

If no sample yet:

```json
{
  "quality": "unavailable",
  "message": "No sample yet",
  "simulated": true,
  "label": "SIMULATED"
}
```

### Sample fields (typical)

| Field | Notes |
|---|---|
| `timestamp` | UTC |
| `source` | `simulator` or `obd` |
| `quality` | `good` \| `stale` \| `estimated` \| `unavailable` |
| `speed_mph`, `rpm`, `fuel_level_pct`, `coolant_c`, `engine_load_pct`, `voltage_v` | Optional floats |
| `mode` | `driving` \| `parked` \| `unknown` (conservative parked policy) |
| `simulated` | boolean |
| `message` | optional human note |

### `WS /ws/telemetry`

Bidirectional WebSocket. Server pushes telemetry samples; client may send text pings to keep alive. Disconnect unregisters the socket.

---

## Trips

### `GET /api/trips`

```json
{
  "trips": [ /* TripSummary API objects; in-progress first if open */ ],
  "count": 0,
  "simulated": true,
  "source": "sqlite",
  "note": "Trip journal from SQLite — SIMULATED provider, not a real vehicle"
}
```

### `GET /api/trips/{trip_id}`

One trip summary or `404` `{ "detail": "Trip not found" }`.

Summaries include start/end, duration, distance, avg/max speed, idle time, fuel estimate status, efficiency score or withhold reason, state (`finalized` / `recovered` / open states, etc.).

### `GET /api/sync?cursor=`

Incremental sync **scaffold** (Pi remains authoritative later):

| Query | Meaning |
|---|---|
| `cursor` | Optional trip id; revisions after that id |

Response sketch:

```json
{
  "cursor": "0",
  "next_cursor": "<last-id-or-same>",
  "revisions": [
    { "id": "...", "state": "finalized", "start": "..." }
  ],
  "note": "Phase 3 sync scaffold — Pi remains authoritative"
}
```

Window size is capped (implementation: 50 after cursor match). Phone export/upsert polish may still be landing separately — do not assume full offline sync UX from this endpoint alone.

---

## Health & maintenance (stubs)

### `GET /api/health`

```json
{
  "dtcs": [],
  "alerts": [],
  "note": "Phase 1 stub — no real diagnostics. Factory warnings remain authoritative.",
  "read_only": true,
  "simulated": true
}
```

### `GET /api/maintenance`

```json
{
  "reminders": [],
  "note": "Phase 1 stub — maintenance reminders arrive later",
  "simulated": true
}
```

Never clears codes or issues vehicle commands.

---

## Voice (stub)

### `POST /api/voice/command`

Body:

```json
{ "intent": "fuel_level", "text": "optional" }
```

Supported intents: `fuel_level`, `range_estimate`, `last_trip`, `check_engine`, `navigate_home`, `pause_spotify`, `end_session`.

Unknown intent → `{ "ok": false, "reply": "I don't support that yet.", ... }`.  
No shell execution, no arbitrary commands.

---

## Simulator scenarios

Only when the active provider is `SimulatorProvider`; otherwise `400`.

### `GET /api/simulator/scenario`

```json
{
  "scenario": "auto",
  "signal_lost": false,
  "valid": ["auto", "parked", "idle", "cruise", "disconnect", "recover"],
  "simulated": true
}
```

### `POST /api/simulator/scenario`

```json
{ "scenario": "cruise" }
```

Invalid name → `400` with detail listing valid scenarios.

---

## Env affecting the server

| Variable | Default | Effect |
|---|---|---|
| `ACCORDOS_HOST` | `0.0.0.0` | Bind host |
| `ACCORDOS_PORT` | `8000` | Bind port |
| `ACCORDOS_DB` | `data/accordos.db` | SQLite path; `:memory:` for ephemeral |

CORS: explicit localhost Vite ports + regex for RFC1918 private IPs. Not for public internet.
