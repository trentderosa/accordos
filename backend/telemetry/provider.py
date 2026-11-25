"""Abstract telemetry provider — simulator and OBD share this contract.

Safety invariants for every implementation:
- Discover capabilities before treating metrics as live
- Read allowlisted PIDs / metrics only (see ``allowlist``)
- Never write to the vehicle bus, clear DTCs, reset ECUs, or issue controls
- Unsupported or undiscovered PIDs → unavailable state (never invent values)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import TelemetrySample


class TelemetryProvider(ABC):
    """Interchangeable vehicle data source (simulator or OBD)."""

    name: str = "provider"

    @abstractmethod
    async def connect(self) -> None:
        """Establish the data source (simulator session or adapter link)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release resources. Must not send vehicle commands."""

    @abstractmethod
    async def discover_capabilities(self) -> dict:
        """Probe or declare what this source can provide.

        Return value should include allowlist ∩ supported metrics, with
        unsupported / undiscovered PIDs marked unavailable. Always
        ``read_only: true`` and ``can_clear_codes: false``.
        """

    @abstractmethod
    async def read(self) -> TelemetrySample:
        """Return the latest sample from allowlisted reads only."""

    def capabilities(self) -> dict:
        """Synchronous snapshot of last discovery (or static declaration).

        Default implementations may override; prefer calling
        ``discover_capabilities`` at connect time and caching the result.
        """
        return {
            "provider": self.name,
            "metrics": [],
            "read_only": True,
            "can_clear_codes": False,
            "can_write": False,
        }

    def is_connected(self) -> bool:
        return False

    def read_dtcs(self) -> list[str]:
        """Active diagnostic codes (read-only Mode 03). Default: none.

        Implementations must never expose a clear/reset path.
        """
        return []


class NullProvider(TelemetryProvider):
    """Placeholder when no provider is configured."""

    name = "null"

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def discover_capabilities(self) -> dict:
        return self.capabilities()

    async def read(self) -> TelemetrySample:
        return TelemetrySample(
            quality="unavailable",
            simulated=False,
            source="obd",
            message="No telemetry provider configured",
        )

    def capabilities(self) -> dict:
        return {
            "provider": self.name,
            "metrics": [],
            "read_only": True,
            "can_clear_codes": False,
            "can_write": False,
        }
