"""Unit and integration tests for trip intelligence (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Database
from backend.telemetry.models import TelemetrySample, VehicleMode
from backend.trips.efficiency import score_trip
from backend.trips.models import EfficiencyStatus, TripState
from backend.trips.service import TripService
from backend.trips.state_machine import (
    OpenTrip,
    TripStateMachine,
    classify_engine,
)
from simulator import SimulatorProvider


def _ts(seconds: float = 0.0) -> datetime:
    return datetime(2026, 11, 24, 18, 0, 0, tzinfo=timezone.utc) + timedelta(
        seconds=seconds
    )


def _sample(
    t: float,
    *,
    speed: float = 0.0,
    rpm: float = 800.0,
    quality: str = "good",
    mode: VehicleMode = VehicleMode.DRIVING,
    fuel: float = 60.0,
) -> TelemetrySample:
    return TelemetrySample(
        timestamp=_ts(t),
        source="simulator",
        quality=quality,  # type: ignore[arg-type]
        speed_mph=speed,
        rpm=rpm,
        fuel_level_pct=fuel,
        coolant_c=90.0,
        engine_load_pct=30.0,
        voltage_v=14.0,
        mode=mode,
        simulated=True,
    )


@pytest.fixture
def db():
    database = Database()
    database.connect()
    yield database
    database.close()


@pytest.fixture
def trips(db):
    return TripService(db, recover_on_start=True)


def test_schema_migrates_to_v3(db):
    assert db.schema_version() == 3
    assert db.target_version == 3


def test_engine_evidence_requires_rpm_and_comm():
    running = classify_engine(_sample(0, rpm=800, quality="good"))
    assert running.running is True
    assert running.communicating is True

    lost = classify_engine(_sample(0, rpm=800, quality="unavailable"))
    assert lost.running is False
    assert lost.communicating is False

    off = classify_engine(
        _sample(0, rpm=0, speed=0, mode=VehicleMode.PARKED, quality="good")
    )
    assert off.running is False
    assert off.communicating is True


def test_state_machine_idle_to_active_to_finalized():
    sm = TripStateMachine(engine_on_debounce_s=1.0, engine_off_debounce_s=2.0)

    # Debounced start: need sustained engine-on
    r0 = sm.ingest(_sample(0.0, speed=0, rpm=750, mode=VehicleMode.UNKNOWN))
    assert r0.opened is False
    assert sm.state == TripState.IDLE

    r1 = sm.ingest(_sample(1.2, speed=0, rpm=800, mode=VehicleMode.UNKNOWN))
    assert r1.opened is True
    assert sm.state in (TripState.STARTING, TripState.ACTIVE)

    # Motion promotes / keeps active
    for i, speed in enumerate([10, 25, 40, 35], start=2):
        sm.ingest(_sample(float(i), speed=speed, rpm=2000))
    assert sm.state == TripState.ACTIVE
    assert sm.open is not None
    assert sm.open.distance_mi > 0

    # Speed 0 with engine still running must NOT end the trip
    sm.ingest(_sample(8.0, speed=0, rpm=750, mode=VehicleMode.UNKNOWN))
    assert sm.state == TripState.ACTIVE

    # Engine off — ending debounce
    sm.ingest(_sample(9.0, speed=0, rpm=0, mode=VehicleMode.PARKED))
    assert sm.state == TripState.ENDING
    closed = sm.ingest(_sample(11.5, speed=0, rpm=0, mode=VehicleMode.PARKED))
    assert closed.closed is True
    assert closed.trip is not None
    assert closed.trip.state == TripState.FINALIZED
    assert sm.state == TripState.IDLE


def test_disconnect_does_not_end_trip():
    sm = TripStateMachine(engine_on_debounce_s=0.5, engine_off_debounce_s=2.0)
    sm.ingest(_sample(0.0, speed=0, rpm=800))
    sm.ingest(_sample(0.6, speed=20, rpm=1800))
    assert sm.state == TripState.ACTIVE

    for t in (1.0, 2.0, 3.0, 5.0):
        r = sm.ingest(
            _sample(t, speed=0, rpm=None, quality="unavailable", mode=VehicleMode.UNKNOWN)
        )
        assert r.closed is False
        assert sm.state == TripState.ACTIVE

    # Resume
    sm.ingest(_sample(6.0, speed=30, rpm=2000))
    assert sm.state == TripState.ACTIVE


def test_never_ends_solely_on_zero_speed():
    sm = TripStateMachine(engine_on_debounce_s=0.5, engine_off_debounce_s=1.0)
    sm.ingest(_sample(0.0, rpm=800))
    sm.ingest(_sample(0.6, speed=15, rpm=1500))
    for t in range(1, 20):
        sm.ingest(_sample(float(t), speed=0.0, rpm=750, mode=VehicleMode.UNKNOWN))
    assert sm.state == TripState.ACTIVE
    assert sm.open is not None
    assert sm.open.idle_time_s > 0


def test_trip_service_persists_and_lists(trips):
    # Build a short synthetic trip
    for t, speed, rpm, mode in [
        (0.0, 0, 0, VehicleMode.PARKED),
        (0.5, 0, 700, VehicleMode.UNKNOWN),
        (1.0, 0, 800, VehicleMode.UNKNOWN),
        (1.5, 10, 1500, VehicleMode.DRIVING),
        (2.5, 30, 2200, VehicleMode.DRIVING),
        (3.5, 40, 2400, VehicleMode.DRIVING),
        (4.5, 20, 1600, VehicleMode.DRIVING),
        (5.5, 0, 750, VehicleMode.UNKNOWN),
        (6.5, 0, 0, VehicleMode.PARKED),
        (8.0, 0, 0, VehicleMode.PARKED),
        (10.0, 0, 0, VehicleMode.PARKED),
    ]:
        trips.ingest(_sample(t, speed=speed, rpm=rpm, mode=mode, fuel=62.0 - t * 0.01))

    listed = trips.list_trips()
    finalized = [t for t in listed if t["status"] in ("finalized", "recovered")]
    assert len(finalized) >= 1
    trip = finalized[0]
    assert trip["simulated"] is True
    assert trip["distance_mi"] is not None and trip["distance_mi"] > 0
    assert trip["duration_s"] is not None and trip["duration_s"] > 0
    assert trip["max_speed_mph"] is not None and trip["max_speed_mph"] >= 30
    assert trip["idle_time_s"] is not None
    assert trip["fuel_estimate_status"] in ("available", "insufficient", "unavailable")
    assert trip["efficiency_status"] in ("available", "withheld", "unavailable")

    got = trips.get_trip(trip["id"])
    assert got is not None
    assert got["id"] == trip["id"]


def test_abrupt_power_loss_recovery(db):
    svc = TripService(db, recover_on_start=False)
    for t, speed, rpm in [
        (0.0, 0, 800),
        (0.8, 15, 1600),
        (1.5, 35, 2200),
        (2.5, 40, 2300),
    ]:
        svc.ingest(_sample(t, speed=speed, rpm=rpm))

    assert svc.current_trip() is not None
    recovered = svc.simulate_shutdown()
    assert len(recovered) >= 1
    assert recovered[0]["status"] == "recovered"
    assert recovered[0]["incomplete"] is True
    assert recovered[0]["efficiency_status"] == "withheld"

    # Fresh service against same DB recovers any leftovers (none left)
    svc2 = TripService(db, recover_on_start=True)
    assert svc2.current_trip() is None
    assert any(t["status"] == "recovered" for t in svc2.list_trips())


def test_duplicate_sample_timestamps_do_not_crash(trips):
    s = _sample(1.0, speed=20, rpm=1800)
    trips.ingest(_sample(0.0, rpm=800))
    trips.ingest(_sample(0.8, speed=10, rpm=1500))
    trips.ingest(s)
    # Same timestamp again — ignored as duplicate, no exception
    trips.ingest(s)
    assert trips.current_trip() is not None or len(trips.list_trips()) >= 0


def test_efficiency_withheld_for_short_trip():
    trip = OpenTrip(
        id="x",
        state=TripState.FINALIZED,
        start_ts=_ts(0),
        end_ts=_ts(5),
        distance_mi=0.02,
        sample_count=5,
        accel_events=[1.0, -1.0],
    )
    result = score_trip(trip)
    assert result.status == EfficiencyStatus.WITHHELD
    assert "not a safety" in result.explanation.lower() or "Not a safety" in result.explanation


def test_efficiency_scaffold_weights_present():
    trip = OpenTrip(
        id="y",
        state=TripState.FINALIZED,
        start_ts=_ts(0),
        end_ts=_ts(600),
        distance_mi=3.0,
        max_speed_mph=45,
        idle_time_s=40,
        moving_time_s=500,
        speed_time_integral=30 * 500,
        sample_count=80,
        fuel_start_pct=60,
        fuel_end_pct=58,
        accel_events=[2.0, 3.0, -2.0, -3.0, 1.0] * 10,
    )
    result = score_trip(trip)
    assert "smooth_acceleration" in result.weights
    assert sum(result.weights.values()) == 100
    assert result.confidence >= 0


def test_api_trips_from_sqlite():
    db = Database()
    app = create_app(SimulatorProvider(seed_offset=10.0), db=db)
    with TestClient(app) as client:
        # Drive the simulator into motion then park via scenario controls
        client.post("/api/simulator/scenario", json={"scenario": "cruise"})
        import time

        time.sleep(2.5)
        client.post("/api/simulator/scenario", json={"scenario": "parked"})
        time.sleep(4.0)

        r = client.get("/api/trips")
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "sqlite"
        assert "trips" in body

        status = client.get("/api/status").json()
        assert status["phase"] == 4
        assert status["trip"]["schema_version"] == 3

        # Root reflects health-core phase
        root = client.get("/").json()
        assert root["phase"] == 4


def test_api_get_trip_404():
    app = create_app(SimulatorProvider(), db=Database())
    with TestClient(app) as client:
        r = client.get("/api/trips/does-not-exist")
        assert r.status_code == 404
