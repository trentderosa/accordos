# AccordOS architecture (Phase 1)

```
SimulatorProvider → TelemetryService → FastAPI REST + WS /ws/telemetry
                                              ↓
                                    React PWA (IndexedDB last-sample glance)
```

- `TelemetryProvider` is the swap point for a future read-only OBD adapter.
- SQLite facade exists under `backend/storage/` (schema version 0); trip persistence is Phase 3.
- IndexedDB on the phone stores the last telemetry sample + connection glance for offline UI (honest “Cached glance” when not live).
- Dev servers bind `0.0.0.0` by default for same-LAN iPhone testing; CORS allows localhost + RFC1918 only.
- Voice / health / maintenance endpoints are stubs that never issue vehicle commands.
