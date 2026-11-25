# OBD provider interface (Phase 2 software prep)

Interchangeable telemetry sources behind `TelemetryProvider`. **No real adapter required** for this work; the OBD path is a graceful stub until Sunday python-OBD wiring.

## Contract

| Method | Purpose |
|---|---|
| `connect()` / `disconnect()` | Open/close the software session (no vehicle writes) |
| `discover_capabilities()` | Allowlist ∩ what the source can actually provide |
| `capabilities()` | Sync snapshot of discovery |
| `read()` | Latest sample from **allowlisted** reads only |
| `read_dtcs()` | Mode 03 style read-only codes (optional) |
| `is_connected()` | Adapter/session truth |

**Never implemented:** clear DTCs, ECU reset, actuator/control commands, or any Mode 04 / write path.

## Env switch

```bash
export ACCORDOS_PROVIDER=SIMULATOR   # default — Mac demos
export ACCORDOS_PROVIDER=OBD         # stub: quality=unavailable, "adapter not connected"
```

Aliases: `SIM` / `SIMULATED` → simulator; `OBDII` / `OBD-II` → obd.

Factory: `backend.telemetry.build_provider()` (used by `create_app()` when no provider is injected).

## Allowlist

Module: `backend/telemetry/allowlist.py`.

- Mode 01 PIDs for RPM, speed, coolant, load, fuel level, voltage
- Mode 03 DTC **read** only
- Unsupported metrics (`odometer`, `oil_life`, `tire_pressure`, …) stay unavailable
- Forbidden modes (e.g. `0x04` clear) are rejected by classification helpers

## Stub behavior (`ObdProvider`)

- Starts without raising so systemd/uvicorn stay up
- `is_connected()` → `False`
- `read()` → `quality="unavailable"`, `source="obd"`, `simulated=False`, message **adapter not connected**
- Capabilities list allowlisted PIDs with `pid_status: unavailable`
- UI chrome shows an **OBD** tag when `simulated === false`

Sunday: replace stub internals with python-OBD serial/USB probe; keep the same ABC and allowlist. Parked, read-only, Gate G2/G3 from [sunday-pi-setup.md](./sunday-pi-setup.md).

## Related

- Architecture swap notes: [architecture.md](./architecture.md)
- Deploy env + units: [../deploy/README.md](../deploy/README.md)
