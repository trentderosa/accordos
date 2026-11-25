# AccordOS architecture (simulator + trip intelligence)

```
SimulatorProvider → TelemetryService → TripService (state machine)
                         ↓                    ↓
              FastAPI REST + WS         SQLite (schema v1)
                         ↓
              React PWA (IndexedDB last-sample glance)
              Parked “Recent trips” ← GET /api/trips
```

- `TelemetryProvider` is the swap point for a future read-only OBD adapter.
- Trip state machine: idle → starting → active → ending → finalized/recovered.
- SQLite under `backend/storage/` (migrations to v1): `trips`, `trip_samples`, `trip_checkpoints`.
- Efficiency score is a scaffold with proposed weights; withheld when confidence is low.
- IndexedDB on the phone stores the last telemetry sample + connection glance for offline UI.
- Dev servers bind `0.0.0.0` by default for same-LAN iPhone testing; CORS allows localhost + RFC1918 only.
- Voice / health / maintenance endpoints are stubs that never issue vehicle commands.
