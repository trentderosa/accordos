"""Telemetry model / stale detection tests."""

from datetime import datetime, timedelta, timezone

from backend.telemetry.models import TelemetrySample


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
