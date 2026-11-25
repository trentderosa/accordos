"""Read-only OBD-II PID / metric allowlist.

AccordOS may query only these Mode 01 (and Mode 03 DTC read) requests.
Anything outside this set is treated as unavailable — never invented,
never written, never cleared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional


@dataclass(frozen=True)
class AllowedPid:
    """One allowlisted diagnostic request."""

    pid: str  # e.g. "010C" (mode + PID hex, uppercase, no spaces)
    metric: str  # TelemetrySample / capabilities metric key
    mode: int  # 0x01 current data, 0x03 DTCs
    description: str
    unit: Optional[str] = None


# Explicit allowlist — expand only with owner review. No write/clear modes.
ALLOWLISTED_PIDS: tuple[AllowedPid, ...] = (
    AllowedPid("010C", "rpm", 0x01, "Engine RPM", "rpm"),
    AllowedPid("010D", "speed_mph", 0x01, "Vehicle speed", "mph"),
    AllowedPid("0105", "coolant_c", 0x01, "Engine coolant temperature", "C"),
    AllowedPid("0104", "engine_load_pct", 0x01, "Calculated engine load", "%"),
    AllowedPid("012F", "fuel_level_pct", 0x01, "Fuel tank level input", "%"),
    AllowedPid("0142", "voltage_v", 0x01, "Control module voltage", "V"),
    # Mode 03: read stored DTCs only (never Mode 04 clear).
    AllowedPid("03", "dtc_codes", 0x03, "Request stored diagnostic trouble codes"),
)

# Metrics standard OBD-II often cannot provide honestly on a 2014 Accord.
UNSUPPORTED_METRICS: FrozenSet[str] = frozenset(
    {
        "odometer",
        "oil_life",
        "tire_pressure",
        "fuel_rate",  # until calibrated / verified on this vehicle
        "maf",
    }
)

# Modes that are forbidden forever in AccordOS (clear / control / program).
FORBIDDEN_MODES: FrozenSet[int] = frozenset(
    {
        0x04,  # Clear/reset DTCs
        0x08,  # Control operation of on-board components
        0x2F,  # Input/output control (UDS-style; defensive)
        0x3E,  # Tester present with session abuse — not used for reads here
    }
)

_PID_INDEX = {entry.pid.upper(): entry for entry in ALLOWLISTED_PIDS}
_METRIC_INDEX = {entry.metric: entry for entry in ALLOWLISTED_PIDS}


def is_pid_allowed(pid: str) -> bool:
    """True if this exact Mode+PID hex is on the allowlist."""
    key = (pid or "").strip().upper().replace(" ", "")
    return key in _PID_INDEX


def is_metric_allowed(metric: str) -> bool:
    return (metric or "").strip() in _METRIC_INDEX


def is_metric_unsupported(metric: str) -> bool:
    return (metric or "").strip() in UNSUPPORTED_METRICS


def is_mode_forbidden(mode: int) -> bool:
    return int(mode) in FORBIDDEN_MODES


def get_pid(pid: str) -> Optional[AllowedPid]:
    key = (pid or "").strip().upper().replace(" ", "")
    return _PID_INDEX.get(key)


def get_metric(metric: str) -> Optional[AllowedPid]:
    return _METRIC_INDEX.get((metric or "").strip())


def allowlisted_metrics() -> list[str]:
    return [entry.metric for entry in ALLOWLISTED_PIDS]


def allowlisted_pid_codes() -> list[str]:
    return [entry.pid for entry in ALLOWLISTED_PIDS]


def filter_requested_pids(requested: Iterable[str]) -> dict[str, str]:
    """Classify requested PIDs as allowed | forbidden | unknown.

    Returns mapping pid → status. Callers must not query non-allowed PIDs.
    """
    out: dict[str, str] = {}
    for raw in requested:
        key = (raw or "").strip().upper().replace(" ", "")
        if not key:
            continue
        # Mode-only or mode+pid
        if key.startswith("04") or key in {"04", "4"}:
            out[key] = "forbidden"
            continue
        try:
            mode = int(key[:2], 16) if len(key) >= 2 else int(key, 16)
        except ValueError:
            out[key] = "unknown"
            continue
        if is_mode_forbidden(mode):
            out[key] = "forbidden"
        elif is_pid_allowed(key):
            out[key] = "allowed"
        else:
            out[key] = "unavailable"
    return out


def capability_snapshot(
    *,
    supported_metrics: Optional[Iterable[str]] = None,
    provider: str = "unknown",
    simulated: bool = False,
    extra: Optional[dict] = None,
) -> dict:
    """Build a capabilities dict: allowlist ∩ actually supported.

    Metrics on the allowlist but not in ``supported_metrics`` are reported
    under ``unavailable_metrics`` with quality semantics = unavailable.
    """
    supported = set(supported_metrics or ())
    available: list[str] = []
    unavailable: list[str] = []
    pid_status: dict[str, str] = {}

    for entry in ALLOWLISTED_PIDS:
        if entry.metric in supported:
            available.append(entry.metric)
            pid_status[entry.pid] = "available"
        else:
            unavailable.append(entry.metric)
            pid_status[entry.pid] = "unavailable"

    payload = {
        "provider": provider,
        "read_only": True,
        "simulated": simulated,
        "can_clear_codes": False,
        "can_write": False,
        "forbidden_modes": sorted(f"0x{m:02X}" for m in FORBIDDEN_MODES),
        "allowlisted_pids": [
            {
                "pid": e.pid,
                "metric": e.metric,
                "mode": e.mode,
                "description": e.description,
                "unit": e.unit,
            }
            for e in ALLOWLISTED_PIDS
        ],
        "metrics": available,
        "unavailable_metrics": unavailable,
        "unsupported": sorted(UNSUPPORTED_METRICS),
        "pid_status": pid_status,
        "notes": (
            "Read allowlisted PIDs only. Never clear codes, reset ECUs, "
            "or issue control commands. Unsupported PIDs stay unavailable."
        ),
    }
    if extra:
        payload.update(extra)
    return payload
