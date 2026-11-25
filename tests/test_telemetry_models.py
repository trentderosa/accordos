"""Telemetry model / stale detection tests."""

from datetime import datetime, timedelta, timezone

from backend.telemetry.models import TelemetrySample, VehicleMode
from backend.telemetry.service import TelemetryService
from simulator import SimulatorProvider


def test_stale_marking():
    old = TelemetrySample(
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=5),
        quality="good",
        speed_mph=30,
        simulated=True,
    )
    marked = old.with_stale_if_needed(max_age_s=3.0)
    assert marked.quality == "stale"
    assert marked.age_seconds() >= 5.0


def test_fresh_sample_stays_good():
    fresh = TelemetrySample(quality="good", speed_mph=10, simulated=True)
    assert fresh.with_stale_if_needed(3.0).quality == "good"


def test_unavailable_not_rewritten_to_stale():
    old = TelemetrySample(
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=10),
        quality="unavailable",
        simulated=True,
        message="SIMULATED · disconnect",
    )
    assert old.with_stale_if_needed(3.0).quality == "unavailable"


def test_default_mode_is_unknown_not_parked():
    sample = TelemetrySample(speed_mph=0.0, rpm=0.0, simulated=True)
    assert sample.mode == VehicleMode.UNKNOWN


def test_service_connection_status_reflects_stale():
    import asyncio

    provider = SimulatorProvider()

    async def _run():
        svc = TelemetryService(provider)
        await svc.start()
        await asyncio.sleep(0.35)
        latest = svc.latest
        assert latest is not None
        # Force an aged sample to verify stale surfacing
        svc._latest = latest.model_copy(
            update={
                "timestamp": datetime.now(timezone.utc) - timedelta(seconds=5),
                "quality": "good",
            }
        )
        status = svc.connection_status
        assert status["stale"] is True
        assert status["provider"] == "simulator"
        await svc.stop()

    asyncio.run(_run())
