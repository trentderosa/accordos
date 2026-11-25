"""Select telemetry provider from environment.

``ACCORDOS_PROVIDER``:
- ``SIMULATOR`` (default) — Mac / Pi without adapter
- ``OBD`` — stub until Sunday python-OBD wiring; honest adapter-not-connected
"""

from __future__ import annotations

import os
from typing import Mapping, Optional

from .obd import ObdProvider
from .provider import TelemetryProvider

# Accepted tokens (case-insensitive).
_SIMULATOR_ALIASES = frozenset({"SIMULATOR", "SIM", "SIMULATED"})
_OBD_ALIASES = frozenset({"OBD", "OBDII", "OBD-II", "OBD_II"})


def normalize_provider_name(raw: Optional[str]) -> str:
    """Return canonical ``simulator`` or ``obd`` from env-ish input."""
    key = (raw or "simulator").strip().upper()
    if not key:
        key = "SIMULATOR"
    if key in _SIMULATOR_ALIASES:
        return "simulator"
    if key in _OBD_ALIASES:
        return "obd"
    raise ValueError(
        f"Unknown ACCORDOS_PROVIDER={raw!r}. "
        "Use SIMULATOR or OBD."
    )


def build_provider(
    name: Optional[str] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> TelemetryProvider:
    """Construct the active provider.

    Preference order: explicit ``name`` → ``ACCORDOS_PROVIDER`` env → simulator.
    """
    environ = env if env is not None else os.environ
    raw = name if name is not None else environ.get("ACCORDOS_PROVIDER", "simulator")
    kind = normalize_provider_name(raw)
    if kind == "obd":
        return ObdProvider()
    # Local import keeps simulator optional for tiny test harnesses.
    from simulator import SimulatorProvider  # noqa: WPS433 — intentional late import

    return SimulatorProvider()
