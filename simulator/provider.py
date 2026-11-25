"""Simulated drive-cycle telemetry provider.

Interchangeable with a future OBD provider via TelemetryProvider.
Produces a repeating cycle: parked → start → accelerate → cruise → decelerate → park.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from backend.telemetry.models import TelemetrySample, VehicleMode
from backend.telemetry.provider import TelemetryProvider

# Drive cycle phase durations (seconds)
PHASES = (
    ("parked", 4.0),
    ("starting", 2.0),
    ("accel", 8.0),
    ("cruise", 12.0),
    ("decel", 6.0),
    ("idle", 4.0),
)
CYCLE_LEN = sum(p[1] for p in PHASES)


def _phase_at(t: float) -> tuple[str, float]:
    """Return (phase_name, progress 0..1) within the cycle."""
    x = t % CYCLE_LEN
    for name, dur in PHASES:
        if x < dur:
            return name, x / dur if dur else 0.0
        x -= dur
    return "parked", 0.0


def _lerp(a: float, b: float, p: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, p))


class SimulatorProvider(TelemetryProvider):
    name = "simulator"

    def __init__(self, seed_offset: float = 0.0) -> None:
        self._connected = False
        self._t0 = time.monotonic() - seed_offset
        self._fuel = 62.0  # percent

    async def connect(self) -> None:
        self._connected = True
        self._t0 = time.monotonic()

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def capabilities(self) -> dict:
        return {
            "provider": self.name,
            "read_only": True,
            "simulated": True,
            "metrics": [
                "speed_mph",
                "rpm",
                "fuel_level_pct",
                "coolant_c",
                "engine_load_pct",
                "voltage_v",
            ],
            "unsupported": ["odometer", "oil_life", "tire_pressure"],
            "notes": "Phase 1 simulator — not real vehicle data",
        }

    async def read(self) -> TelemetrySample:
        if not self._connected:
            return TelemetrySample(
                quality="unavailable",
                source="simulator",
                simulated=True,
                message="Simulator not connected",
            )

        elapsed = time.monotonic() - self._t0
        phase, p = _phase_at(elapsed)
        speed, rpm, load, mode = self._kinematics(phase, p)

        # Slow fuel burn while moving
        if speed and speed > 0.5:
            self._fuel = max(5.0, self._fuel - 0.002)
        coolant = 85.0 if mode != VehicleMode.PARKED else _lerp(25.0, 70.0, min(1.0, elapsed / 30.0))
        voltage = 14.2 if rpm and rpm > 500 else 12.4

        return TelemetrySample(
            timestamp=datetime.now(timezone.utc),
            source="simulator",
            quality="good",
            speed_mph=round(speed, 1) if speed is not None else None,
            rpm=round(rpm) if rpm is not None else None,
            fuel_level_pct=round(self._fuel, 1),
            coolant_c=round(coolant, 1),
            engine_load_pct=round(load, 1) if load is not None else None,
            voltage_v=round(voltage, 1),
            mode=mode,
            simulated=True,
            message=f"SIMULATED · {phase}",
        )

    @staticmethod
    def _kinematics(
        phase: str, p: float
    ) -> tuple[float | None, float | None, float | None, VehicleMode]:
        if phase == "parked":
            return 0.0, 0.0, 0.0, VehicleMode.PARKED
        if phase == "starting":
            return 0.0, _lerp(0, 800, p), _lerp(0, 20, p), VehicleMode.UNKNOWN
        if phase == "accel":
            ease = 0.5 - 0.5 * math.cos(math.pi * p)
            return _lerp(0, 55, ease), _lerp(800, 3200, ease), _lerp(25, 70, ease), VehicleMode.DRIVING
        if phase == "cruise":
            wobble = 2.0 * math.sin(p * math.pi * 4)
            return 55.0 + wobble, 2200 + 80 * math.sin(p * math.pi * 2), 35.0, VehicleMode.DRIVING
        if phase == "decel":
            ease = p * p
            return _lerp(55, 0, ease), _lerp(2200, 750, ease), _lerp(20, 10, ease), VehicleMode.DRIVING
        # idle — engine on, speed 0; NOT parked (conservative policy)
        return 0.0, 750.0, 12.0, VehicleMode.UNKNOWN
