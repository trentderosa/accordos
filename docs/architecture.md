# AccordOS architecture (Phase 1)

```
SimulatorProvider → TelemetryService → FastAPI REST + WS /ws/telemetry
                                              ↓
                                    React PWA (IndexedDB scaffold)
```

- `TelemetryProvider` is the swap point for a future read-only OBD adapter.
- SQLite facade exists under `backend/storage/` (schema version 0); trip persistence is Phase 3.
- Voice / health / maintenance endpoints are stubs that never issue vehicle commands.
