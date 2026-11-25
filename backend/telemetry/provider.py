"""Abstract telemetry provider — simulator and future OBD share this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import TelemetrySample


class TelemetryProvider(ABC):
    """Interchangeable vehicle data source."""

    name: str = "provider"

    @abstractmethod
    async def connect(self) -> None:
        """Establish the data source."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release resources."""

    @abstractmethod
    async def read(self) -> TelemetrySample:
        """Return the latest sample (may be synthetic)."""

    @abstractmethod
    def capabilities(self) -> dict:
        """Declare supported metrics and constraints."""

    def is_connected(self) -> bool:
        return False


class NullProvider(TelemetryProvider):
    """Placeholder when no provider is configured."""

    name = "null"

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def read(self) -> TelemetrySample:
        return TelemetrySample(
            quality="unavailable",
            simulated=False,
            source="obd",
            message="No telemetry provider configured",
        )

    def capabilities(self) -> dict:
        return {"provider": self.name, "metrics": [], "read_only": True}
