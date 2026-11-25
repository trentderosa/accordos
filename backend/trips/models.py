"""Trip journal models and state definitions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TripState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    ENDING = "ending"
    FINALIZED = "finalized"
    RECOVERED = "recovered"


class FuelEstimateStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT = "insufficient"


class EfficiencyStatus(str, Enum):
    AVAILABLE = "available"
    WITHHELD = "withheld"
    UNAVAILABLE = "unavailable"


# Proposed initial weights from product handoff §7 (scaffold only).
EFFICIENCY_WEIGHTS = {
    "smooth_acceleration": 25,
    "smooth_deceleration": 25,
    "fuel_efficiency": 25,
    "engine_efficiency": 15,
    "idling_efficiency": 10,
}


class TripSummary(BaseModel):
    id: str
    state: TripState
    start: str
    end: Optional[str] = None
    duration_s: Optional[float] = None
    duration_min: Optional[float] = None
    distance_mi: Optional[float] = None
    avg_speed_mph: Optional[float] = None
    max_speed_mph: Optional[float] = None
    idle_time_s: Optional[float] = None
    idle_time_min: Optional[float] = None
    fuel_used_pct: Optional[float] = None
    fuel_estimate_status: FuelEstimateStatus = FuelEstimateStatus.UNAVAILABLE
    efficiency_score: Optional[float] = None
    efficiency_confidence: Optional[float] = None
    efficiency_status: EfficiencyStatus = EfficiencyStatus.WITHHELD
    efficiency_detail: Optional[dict[str, Any]] = None
    incomplete: bool = False
    simulated: bool = True
    source: str = "simulator"
    title: Optional[str] = None
    note: Optional[str] = None
    label: str = "SIMULATED"
    status: Optional[str] = None  # alias of state for UI compatibility

    def to_api(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["status"] = self.state.value
        if self.simulated:
            data["label"] = "SIMULATED"
        return data


class EfficiencyResult(BaseModel):
    score: Optional[float] = None
    confidence: float = 0.0
    status: EfficiencyStatus = EfficiencyStatus.WITHHELD
    weights: dict[str, int] = Field(default_factory=lambda: dict(EFFICIENCY_WEIGHTS))
    subscores: dict[str, Optional[float]] = Field(default_factory=dict)
    coverage: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""
