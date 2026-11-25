"""Stub OBD-II provider — honest “adapter not connected” until Sunday wiring.

Real ``python-OBD`` integration is intentionally deferred. This stub:
- Implements the same ``TelemetryProvider`` contract as the simulator
- Never writes, clears codes, or issues control commands
- Surfaces allowlisted PIDs as unavailable until a real adapter is linked
"""

from __future__ import annotations

from datetime import datetime, timezone

from .allowlist import capability_snapshot
from .models import TelemetrySample, VehicleMode
from .provider import TelemetryProvider

ADAPTER_NOT_CONNECTED = "adapter not connected"


class ObdProvider(TelemetryProvider):
    """Read-only OBD placeholder. Fails gracefully without hardware."""

    name = "obd"

    def __init__(self) -> None:
        self._session_open = False
        self._caps: dict = capability_snapshot(
            supported_metrics=(),
            provider=self.name,
            simulated=False,
            extra={
                "adapter_connected": False,
                "python_obd": "pending_sunday",
                "message": (
                    f"{ADAPTER_NOT_CONNECTED} — "
                    "python-OBD wiring lands with hardware on Sunday"
                ),
            },
        )

    async def connect(self) -> None:
        """Open a software session only — no serial/USB adapter yet.

        ``is_connected()`` stays False so callers see honest adapter state.
        """
        self._session_open = True
        await self.discover_capabilities()

    async def disconnect(self) -> None:
        self._session_open = False

    def is_connected(self) -> bool:
        # Honest until real adapter + python-OBD probe succeeds.
        return False

    async def discover_capabilities(self) -> dict:
        """Stub discovery: allowlist known, zero PIDs supported without adapter."""
        self._caps = capability_snapshot(
            supported_metrics=(),
            provider=self.name,
            simulated=False,
            extra={
                "adapter_connected": False,
                "session_open": self._session_open,
                "python_obd": "pending_sunday",
                "read_dtcs": False,
                "message": (
                    f"{ADAPTER_NOT_CONNECTED} — "
                    "capability probe deferred until python-OBD wiring"
                ),
            },
        )
        return dict(self._caps)

    def capabilities(self) -> dict:
        return dict(self._caps)

    def read_dtcs(self) -> list[str]:
        # No Mode 03 traffic until adapter is real; never Mode 04 clear.
        return []

    async def read(self) -> TelemetrySample:
        """Always unavailable until a real adapter is connected."""
        return TelemetrySample(
            timestamp=datetime.now(timezone.utc),
            source="obd",
            quality="unavailable",
            speed_mph=None,
            rpm=None,
            fuel_level_pct=None,
            coolant_c=None,
            engine_load_pct=None,
            voltage_v=None,
            mode=VehicleMode.UNKNOWN,
            simulated=False,
            message=ADAPTER_NOT_CONNECTED,
        )
