"""Shared telemetry data models (API contract)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VehicleMode(str, Enum):
    """Conservative parked-state policy: PARKED only when explicitly parked."""

    DRIVING = "driving"
    PARKED = "parked"
    UNKNOWN = "unknown"


class TelemetrySample(BaseModel):
    """One telemetry snapshot. Units are normalized for the API."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Literal["simulator", "obd"] = "simulator"
    quality: Literal["good", "stale", "estimated", "unavailable"] = "good"
    speed_mph: Optional[float] = None
    rpm: Optional[float] = None
    fuel_level_pct: Optional[float] = None
    coolant_c: Optional[float] = None
    engine_load_pct: Optional[float] = None
    voltage_v: Optional[float] = None
    mode: VehicleMode = VehicleMode.UNKNOWN
    simulated: bool = True
    message: Optional[str] = None

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        ts = self.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (now - ts).total_seconds())

    def with_stale_if_needed(self, max_age_s: float = 3.0) -> "TelemetrySample":
        if self.age_seconds() > max_age_s and self.quality == "good":
            return self.model_copy(update={"quality": "stale"})
        return self
