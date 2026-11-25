"""Simulated drive-cycle telemetry provider.

Interchangeable with a future OBD provider via TelemetryProvider.
Default cycle: parked → start → accelerate → cruise → decelerate → idle.
Demo scenarios can pin idle / cruise / parked / disconnect / recover.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Literal

from backend.telemetry.allowlist import capability_snapshot
from backend.telemetry.models import TelemetrySample, VehicleMode
from backend.telemetry.provider import TelemetryProvider

# Simulator always "supports" the core allowlisted live metrics (fake values).
_SIM_SUPPORTED_METRICS = (
    "speed_mph",
    "rpm",
    "fuel_level_pct",
    "coolant_c",
    "engine_load_pct",
    "voltage_v",
    "dtc_codes",
)

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

ScenarioName = Literal[
    "auto",
    "parked",
    "idle",
    "cruise",
    "disconnect",
    "recover",
    "healthy",
    "check_engine",
    "misfire",
    "overheat",
    "low_voltage",
]
VALID_SCENARIOS = (
    "auto",
    "parked",
    "idle",
    "cruise",
    "disconnect",
    "recover",
    "healthy",
    "check_engine",
    "misfire",
    "overheat",
    "low_voltage",
)

# Fake DTC sets for demo scenarios — read-only; never cleared by AccordOS.
SCENARIO_DTCS: dict[str, tuple[str, ...]] = {
    "healthy": (),
    "check_engine": ("P0420",),
    "misfire": ("P0300", "P0171"),
    "overheat": ("P0128",),
    "low_voltage": ("P0562",),
}


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
        self._scenario: ScenarioName = "auto"
        self._signal_lost = False
        self._elapsed_hold: float | None = None
        self._dtcs: list[str] = []

    async def connect(self) -> None:
        self._connected = True
        self._t0 = time.monotonic()
        self._signal_lost = False
        await self.discover_capabilities()

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and not self._signal_lost

    async def discover_capabilities(self) -> dict:
        """Simulator declares the full allowlisted metric set as available."""
        return self.capabilities()

    def scenario(self) -> dict:
        return {
            "scenario": self._scenario,
            "signal_lost": self._signal_lost,
            "valid": list(VALID_SCENARIOS),
            "simulated": True,
        }

    def set_scenario(self, name: str) -> dict:
        key = (name or "").strip().lower()
        if key not in VALID_SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'. Valid: {', '.join(VALID_SCENARIOS)}")

        if key == "recover":
            # Resume auto cycle from where we left off (or restart if unknown).
            if self._elapsed_hold is not None:
                self._t0 = time.monotonic() - self._elapsed_hold
            else:
                self._t0 = time.monotonic()
            self._elapsed_hold = None
            self._signal_lost = False
            self._scenario = "auto"
            # Recover restores the drive cycle only — DTCs are not cleared here
            # (AccordOS never clears codes; ECU-side clear is out of scope).
        elif key == "disconnect":
            if not self._signal_lost:
                self._elapsed_hold = time.monotonic() - self._t0
            self._signal_lost = True
            self._scenario = "disconnect"
        else:
            self._signal_lost = False
            self._elapsed_hold = None
            self._scenario = key  # type: ignore[assignment]
            # Pin scenario start so demos are immediate and stable.
            if key != "auto":
                self._t0 = time.monotonic()
            if key in SCENARIO_DTCS:
                self._dtcs = list(SCENARIO_DTCS[key])
            elif key == "auto":
                # Auto cycle does not invent faults.
                self._dtcs = []

        return self.scenario()

    def read_dtcs(self) -> list[str]:
        """Return active simulated diagnostic codes (read-only)."""
        return list(self._dtcs)

    def capabilities(self) -> dict:
        return capability_snapshot(
            supported_metrics=_SIM_SUPPORTED_METRICS,
            provider=self.name,
            simulated=True,
            extra={
                "scenarios": list(VALID_SCENARIOS),
                "read_dtcs": True,
                "notes": (
                    "Simulator — not real vehicle data. "
                    "DTC scenarios are fake and read-only; AccordOS never clears codes."
                ),
            },
        )

    async def read(self) -> TelemetrySample:
        if not self._connected or self._signal_lost:
            return TelemetrySample(
                quality="unavailable",
                source="simulator",
                simulated=True,
                mode=VehicleMode.UNKNOWN,
                message=(
                    "SIMULATED · disconnect — telemetry signal lost"
                    if self._signal_lost
                    else "Simulator not connected"
                ),
            )

        elapsed = time.monotonic() - self._t0
        phase, p = self._resolve_phase(elapsed)
        speed, rpm, load, mode = self._kinematics(phase, p)

        # Slow fuel burn while moving
        if speed and speed > 0.5:
            self._fuel = max(5.0, self._fuel - 0.002)
        coolant = 85.0 if mode != VehicleMode.PARKED else _lerp(25.0, 70.0, min(1.0, elapsed / 30.0))
        voltage = 14.2 if rpm and rpm > 500 else 12.4

        # Fault demos bend vitals while keeping the drive cycle readable.
        if self._scenario == "overheat":
            coolant = _lerp(95.0, 112.0, min(1.0, elapsed / 8.0))
            mode = VehicleMode.PARKED if phase == "parked" else mode
        elif self._scenario == "low_voltage":
            voltage = _lerp(12.0, 11.5, min(1.0, elapsed / 6.0))
        elif self._scenario in ("check_engine", "misfire", "healthy"):
            # Keep parked for the health panel demo unless user switches elsewhere.
            if self._scenario != "healthy" or phase == "parked":
                pass

        label = phase if self._scenario == "auto" else self._scenario
        dtc_note = f" · {len(self._dtcs)} DTC" if self._dtcs else ""
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
            message=f"SIMULATED · {label}{dtc_note}",
        )

    def _resolve_phase(self, elapsed: float) -> tuple[str, float]:
        if self._scenario == "parked":
            return "parked", min(1.0, elapsed / 4.0)
        if self._scenario == "idle":
            return "idle", min(1.0, elapsed / 4.0)
        if self._scenario == "cruise":
            return "cruise", (elapsed % 12.0) / 12.0
        # Health demos default to parked so the panel is visible immediately.
        if self._scenario in ("healthy", "check_engine", "misfire", "overheat", "low_voltage"):
            return "parked", min(1.0, elapsed / 4.0)
        return _phase_at(elapsed)

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
