# AccordOS API (as implemented)

Base URL (Mac/Pi local): `http://127.0.0.1:8000` or `http://<lan-ip>:8000`  
Interactive docs: `/docs`  
API version reported in status/root: **0.5.0** (phase `5` light = encoded Waze/Apple Maps deep links + Spotify open/Siri stub on top of health + voice; no paid APIs / no client secrets; wake word / ASR / TTS not included; Pi hardware still Phase 2).

All telemetry today is **SIMULATED** unless a future OBD provider is injected. Most endpoints remain trusted-LAN only. **Voice command POST** is authenticated-or-local (loopback free; non-local requires `ACCORDOS_VOICE_TOKEN`).

## Root

### `GET /`

```json
{
  "app": "AccordOS",
  "phase": 5,
  "phase_note": "Phase 5 light: maps deep-link stubs + Spotify open/Siri stub; health + voice on simulator; Pi hardware still Phase 2",
  "api_version": "0.5.0",
  "docs": "/docs",
  "ws": "/ws/telemetry",
  "note": "SIMULATED telemetry — not a real vehicle",
  "infotainment": {
    "maps": "deep_link_stubs",
    "spotify": "open_siri_stub",
    "oauth_pkce": "documented_not_wired"
  },
  "lan": "..."
}
```

---

## Capabilities & status

### `GET /api/capabilities`

Provider-declared metrics and constraints (`read_only`, simulator flags, `can_clear_codes: false`). Shape comes from `TelemetryProvider.capabilities()`.

### `GET /api/status`

```json
{
  "app": "AccordOS",
  "phase": 5,
  "api_version": "0.5.0",
  "connection": { "...": "from TelemetryService" },
  "trip": {
    "current": { "...": "in-progress trip or null" },
    "schema_version": 3,
    "sync": "GET /api/sync?cursor="
  },
  "health": {
    "read_only": true,
    "can_clear_codes": false
  },
  "infotainment": {
    "maps": "deep_link_stubs",
    "spotify": "open_siri_stub",
    "oauth_pkce": "documented_not_wired",
    "docs": "docs/infotainment.md"
  },
  "voice": {
    "intents": ["check_engine", "end_session", "fuel_level", "..."],
    "followup_timeout_s": 15,
    "auth": "local_or_bearer",
    "wake_word": false,
    "llm": false,
    "audio_feasibility_gate": "open"
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

Summaries include start/end, duration, distance, avg/max speed, idle time, fuel estimate status, efficiency score or withhold reason, state (`finalized` / `recovered` / open states, etc.), and monotonic `revision` when closed.

### `GET /api/sync?cursor=`

Pi-authoritative incremental sync (integer revision cursor):

| Query | Meaning |
|---|---|
| `cursor` | Last applied integer revision (`0` or omit to start) |
| `limit` | Optional page size (implementation default/cap 50) |

```json
{
  "cursor": "0",
  "next_cursor": "12",
  "has_more": false,
  "revisions": [
    {
      "revision": 12,
      "op": "upsert",
      "id": "<trip-id>",
      "trip": { "...": "full TripSummary" }
    }
  ],
  "note": "Upsert each revision.trip by trip.id. Pi remains authoritative."
}
```

---

## Health & maintenance

Read-only. **Never** clears codes, resets ECUs, or issues control commands. Every code payload sets `interpretation: "code"` and explains that a DTC is **not** a confirmed diagnosis. Factory warnings remain authoritative.

### `GET /api/health`

SQLite-backed diagnostic history + telemetry trends (schema v3).

```json
{
  "dtcs": [
    {
      "code": "P0420",
      "title": "Catalyst system efficiency below threshold (Bank 1)",
      "summary": "...",
      "common_causes": ["..."],
      "interpretation": "code",
      "interpretation_note": "This is a diagnostic trouble code, not a confirmed diagnosis. ...",
      "severity": "warning",
      "system": "emissions",
      "reference_found": true,
      "status": "active",
      "first_seen": "...",
      "last_seen": "...",
      "simulated": true
    }
  ],
  "alerts": [
    {
      "id": "dtc:active",
      "severity": "warning",
      "title": "Diagnostic codes present",
      "detail": "...",
      "active": true,
      "simulated": true
    }
  ],
  "trends": [
    {
      "metric": "coolant_c",
      "unit": "°C",
      "label": "Coolant",
      "latest": 85.0,
      "baseline": 84.5,
      "status": "ok",
      "message": "...",
      "points": [{ "ts": "...", "value": 85.0 }],
      "hysteresis_note": "Watch 100.0°C; alert 108.0°C; clears with hysteresis."
    }
  ],
  "active_dtc_count": 1,
  "read_only": true,
  "can_clear_codes": false,
  "simulated": true,
  "schema_version": 3,
  "disclaimer": "Diagnostic codes are stored fault flags — not confirmed diagnoses. ...",
  "note": "SIMULATED health — not a real vehicle scan"
}
```

When the simulator stops reporting a code, the row becomes `historical` — history is retained; AccordOS still never clears the ECU.

### `GET /api/maintenance`

```json
{
  "reminders": [
    {
      "id": "...",
      "title": "Engine oil & filter",
      "kind": "oil_change",
      "due_label": "Every 5,000 mi or 6 months (owner interval)",
      "interval_mi": 5000,
      "interval_months": 6,
      "last_service_label": "...",
      "status": "due_soon",
      "note": "Interval is user-provided — not a live odometer reading.",
      "simulated": true,
      "source": "user_interval"
    }
  ],
  "simulated": true,
  "note": "Reminders use user-provided intervals / known service labels — not fabricated odometer readings."
}
```

There is **no** clear-DTC endpoint.

---

## Voice (deterministic intents)

See [voice-intents.md](./voice-intents.md). Audio feasibility gate remains **open** (PWA TTS / background unproven).

### `POST /api/voice/command`

**Auth:** loopback client allowed without a token; non-local clients need `Authorization: Bearer <ACCORDOS_VOICE_TOKEN>` (set env `ACCORDOS_VOICE_TOKEN`).

Body — provide `intent` and/or `text` (text is routed with deterministic patterns + ~15s follow-up context):

```json
{ "text": "How much fuel is left?" }
```

```json
{ "intent": "fuel_level", "text": "optional" }
```

Supported intents: `fuel_level`, `range_estimate`, `last_trip`, `check_engine`, `navigate_home`, `pause_spotify`, `end_session`.

Unknown → `{ "ok": false, "reply": "...", "shell_executed": false, ... }`.  
Always `shell_executed: false`. No arbitrary commands. Navigate home returns **encoded** Waze/Apple Maps deep-link stubs (`launched: false`). Spotify returns open/Siri stub (`executed: false`, no client secrets). See [infotainment.md](./infotainment.md).

### `GET /api/voice/briefing`

Startup briefing from fuel + health (maintenance note when relevant). Never includes previous-trip fuel cost. Documents the open audio feasibility gate in `note`.

### `GET /api/voice/session`

Follow-up window snapshot, supported intents, `audio_feasibility_gate: "open"`.

---

## Simulator scenarios

Only when the active provider is `SimulatorProvider`; otherwise `400`.

### `GET /api/simulator/scenario`

```json
{
  "scenario": "auto",
  "signal_lost": false,
  "valid": [
    "auto", "parked", "idle", "cruise", "disconnect", "recover",
    "healthy", "check_engine", "misfire", "overheat", "low_voltage"
  ],
  "simulated": true
}
```

### `POST /api/simulator/scenario`

```json
{ "scenario": "check_engine" }
```

| Scenario | Effect |
|---|---|
| `healthy` | Parked, no active DTCs (prior codes become historical) |
| `check_engine` | Parked + active `P0420` |
| `misfire` | Parked + `P0300`, `P0171` |
| `overheat` | Parked + rising coolant toward alert thresholds |
| `low_voltage` | Parked + low system voltage |
| `recover` | Restores drive cycle signal — **does not clear DTCs** |

Invalid name → `400` with detail listing valid scenarios.

---

## Env affecting the server

| Variable | Default | Effect |
|---|---|---|
| `ACCORDOS_HOST` | `0.0.0.0` | Bind host |
| `ACCORDOS_PORT` | `8000` | Bind port |
| `ACCORDOS_DB` | `data/accordos.db` | SQLite path; `:memory:` for ephemeral |
| `ACCORDOS_VOICE_TOKEN` | *(unset)* | Bearer token required for non-local `POST /api/voice/command` |

CORS: explicit localhost Vite ports + regex for RFC1918 private IPs. Not for public internet.

SQLite schema **v3** adds `diagnostic_events`, `telemetry_trend_samples`, `trend_state`, `maintenance_reminders`, `health_alerts` on top of trips/sync tables.
