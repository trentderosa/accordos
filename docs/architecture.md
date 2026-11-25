# AccordOS architecture (simulator + trip intelligence + sync)

```
SimulatorProvider → TelemetryService → TripService (state machine)
                         ↓                    ↓
              FastAPI REST + WS         SQLite (schema v2)
                         ↓                    ↓
              GET /api/sync?cursor=     revision upserts
                         ↓
              React PWA → IndexedDB trip replica + glance cache
              Parked “Recent trips” ← replica (offline after sync)
              Export JSON/CSV ↔ restore
```

- `TelemetryProvider` is the swap point for a future read-only OBD adapter.
- Trip state machine: idle → starting → active → ending → finalized/recovered.
- SQLite under `backend/storage/` (migrations to v2): `trips` (+ `revision`), `trip_samples`, `trip_checkpoints`, `sync_meta`.
- Sync is Pi-authoritative with monotonic revisions and idempotent upserts by stable trip id.
- Efficiency score is a scaffold with proposed weights; withheld when confidence is low.
- IndexedDB stores last telemetry glance plus synced trip history for offline UI.
- Dev servers bind `0.0.0.0` by default for same-LAN iPhone testing; CORS allows localhost + RFC1918 only.
- Voice / health / maintenance endpoints are stubs that never issue vehicle commands.
