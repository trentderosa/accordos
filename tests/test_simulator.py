"""Unit tests for the simulator provider contract."""

from __future__ import annotations

import asyncio

from backend.telemetry.models import VehicleMode
from simulator import SimulatorProvider


def test_capabilities_mark_simulated():
    p = SimulatorProvider()
    caps = p.capabilities()
    assert caps["simulated"] is True
    assert caps["read_only"] is True
    assert "speed_mph" in caps["metrics"]
    assert "odometer" in caps["unsupported"]


def test_disconnected_read_unavailable():
    p = SimulatorProvider()

    async def _run():
        sample = await p.read()
        assert sample.quality == "unavailable"
        assert sample.simulated is True

    asyncio.run(_run())


def test_drive_cycle_produces_samples():
    p = SimulatorProvider()

    async def _run():
        await p.connect()
        assert p.is_connected()
        samples = [await p.read() for _ in range(5)]
        await p.disconnect()
        assert all(s.simulated for s in samples)
        assert all(s.source == "simulator" for s in samples)
        assert all(s.quality == "good" for s in samples)
        assert any(s.fuel_level_pct is not None for s in samples)

    asyncio.run(_run())


def test_parked_not_inferred_from_zero_speed_alone():
    """Idle phase has speed 0 but mode must not be PARKED (conservative policy)."""
    # seed_offset into idle phase: parked(4)+starting(2)+accel(8)+cruise(12)+decel(6)=32 → idle
    p = SimulatorProvider(seed_offset=33.0)

    async def _run():
        await p.connect()
        # Override t0 after connect using seed
        p._t0 = __import__("time").monotonic() - 33.0
        sample = await p.read()
        await p.disconnect()
        assert sample.speed_mph == 0.0
        assert sample.mode != VehicleMode.PARKED
        assert sample.mode == VehicleMode.UNKNOWN

    asyncio.run(_run())


def test_parked_phase_is_parked():
    p = SimulatorProvider(seed_offset=0.5)

    async def _run():
        await p.connect()
        p._t0 = __import__("time").monotonic() - 0.5
        sample = await p.read()
        await p.disconnect()
        assert sample.mode == VehicleMode.PARKED
        assert sample.speed_mph == 0.0

    asyncio.run(_run())
