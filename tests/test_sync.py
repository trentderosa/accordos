"""Pi-authoritative sync, idempotent upserts, export round-trip."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Database
from backend.telemetry.models import TelemetrySample, VehicleMode
from backend.trips.models import (
    EfficiencyStatus,
    FuelEstimateStatus,
    TripState,
    TripSummary,
)
from backend.trips.service import TripService
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
    mode: VehicleMode = VehicleMode.DRIVING,
) -> TelemetrySample:
    return TelemetrySample(
        timestamp=_ts(t),
        source="simulator",
        quality="good",
        speed_mph=speed,
        rpm=rpm,
        fuel_level_pct=60.0,
        coolant_c=90.0,
        engine_load_pct=30.0,
        voltage_v=14.0,
        mode=mode,
        simulated=True,
    )


def _drive_one(svc: TripService, offset: float = 0.0) -> dict:
    # Engine-off debounce is ~3s — hold parked long enough to finalize.
    for t, speed, rpm, mode in [
        (offset + 0.0, 0, 0, VehicleMode.PARKED),
        (offset + 0.5, 0, 700, VehicleMode.UNKNOWN),
        (offset + 1.0, 0, 800, VehicleMode.UNKNOWN),
        (offset + 1.5, 15, 1600, VehicleMode.DRIVING),
        (offset + 2.5, 35, 2200, VehicleMode.DRIVING),
        (offset + 3.5, 30, 2000, VehicleMode.DRIVING),
        (offset + 4.5, 20, 1600, VehicleMode.DRIVING),
        (offset + 5.5, 0, 750, VehicleMode.UNKNOWN),
        (offset + 6.5, 0, 0, VehicleMode.PARKED),
        (offset + 8.0, 0, 0, VehicleMode.PARKED),
        (offset + 10.0, 0, 0, VehicleMode.PARKED),
    ]:
        closed = svc.ingest(_sample(t, speed=speed, rpm=rpm, mode=mode))
        if closed and closed.get("status") in ("finalized", "recovered"):
            return closed
    listed = [t for t in svc.list_trips() if t["status"] in ("finalized", "recovered")]
    assert listed, "expected a finalized trip"
    return listed[0]


@pytest.fixture
def trips():
    db = Database()
    db.connect()
    svc = TripService(db, recover_on_start=True)
    yield svc
    db.close()


def test_sync_assigns_monotonic_revisions(trips):
    a = _drive_one(trips, 0.0)
    b = _drive_one(trips, 20.0)
    assert a["revision"] is not None
    assert b["revision"] is not None
    assert b["revision"] > a["revision"]


def test_sync_cursor_pagination(trips):
    ids = []
    for i in range(5):
        ids.append(_drive_one(trips, offset=i * 30.0)["id"])

    page1 = trips.sync("0", limit=2)
    assert page1["cursor"] == "0"
    assert page1["has_more"] is True
    assert len(page1["revisions"]) == 2
    assert page1["semantics"]["idempotent_upserts"] is True
    assert page1["semantics"]["authoritative"] == "pi"
    for rev in page1["revisions"]:
        assert rev["op"] == "upsert"
        assert rev["entity"] == "trip"
        assert rev["trip"]["id"] == rev["id"]
        assert rev["revision"] == rev["trip"]["revision"]

    page2 = trips.sync(page1["next_cursor"], limit=2)
    assert page2["has_more"] is True
    assert len(page2["revisions"]) == 2
    assert {r["id"] for r in page1["revisions"]}.isdisjoint(
        {r["id"] for r in page2["revisions"]}
    )

    page3 = trips.sync(page2["next_cursor"], limit=2)
    assert page3["has_more"] is False
    assert len(page3["revisions"]) == 1

    all_ids = [
        r["id"]
        for page in (page1, page2, page3)
        for r in page["revisions"]
    ]
    assert set(all_ids) == set(ids)


def test_duplicate_sync_is_idempotent(trips):
    trip = _drive_one(trips)
    first = trips.sync("0", limit=50)
    second = trips.sync("0", limit=50)
    assert first["revisions"] == second["revisions"]
    assert first["next_cursor"] == second["next_cursor"]

    replica: dict[str, dict] = {}
    for _ in range(2):
        for rev in first["revisions"]:
            replica[rev["id"]] = rev["trip"]
    assert len(replica) == 1
    assert replica[trip["id"]]["revision"] == trip["revision"]


def test_sync_after_cursor_skips_prior(trips):
    first = _drive_one(trips, 0.0)
    second = _drive_one(trips, 30.0)
    page = trips.sync(str(first["revision"]), limit=50)
    assert len(page["revisions"]) == 1
    assert page["revisions"][0]["id"] == second["id"]
    assert page["has_more"] is False


def test_sync_api_and_bad_cursor():
    db = Database()
    app = create_app(SimulatorProvider(), db=db)
    with TestClient(app) as client:
        svc: TripService = app.state.trips
        _drive_one(svc)
        _drive_one(svc, 25.0)

        ok = client.get("/api/sync", params={"cursor": "0", "limit": 1})
        assert ok.status_code == 200
        body = ok.json()
        assert body["has_more"] is True
        assert len(body["revisions"]) == 1
        assert "idempotent_upserts" in body["semantics"]

        nxt = client.get(
            "/api/sync",
            params={"cursor": body["next_cursor"], "limit": 10},
        )
        assert nxt.status_code == 200
        assert nxt.json()["has_more"] is False

        bad = client.get("/api/sync", params={"cursor": "not-a-rev"})
        assert bad.status_code == 400


def test_offline_read_after_sync_replica(trips):
    """Phone replica: after sync, trips remain readable without further Pi calls."""
    trip = _drive_one(trips)
    page = trips.sync("0")
    replica = {r["id"]: r["trip"] for r in page["revisions"]}

    offline_list = sorted(
        replica.values(),
        key=lambda t: t.get("start") or "",
        reverse=True,
    )
    assert len(offline_list) >= 1
    assert offline_list[0]["id"] == trip["id"]
    assert offline_list[0]["distance_mi"] == trip["distance_mi"]


def test_export_json_csv_round_trip(trips):
    a = _drive_one(trips, 0.0)
    b = _drive_one(trips, 40.0)
    page = trips.sync("0")
    trips_payload = [r["trip"] for r in page["revisions"]]

    doc = {
        "format": "accordos-trips",
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "trips": trips_payload,
    }
    raw = json.dumps(doc)
    loaded = json.loads(raw)
    assert loaded["format"] == "accordos-trips"
    by_id = {t["id"]: t for t in loaded["trips"]}
    assert by_id[a["id"]]["revision"] == a["revision"]
    assert by_id[b["id"]]["distance_mi"] == b["distance_mi"]

    other = Database()
    other.connect()
    dest = TripService(other, recover_on_start=False)
    for t in loaded["trips"]:
        summary = TripSummary(
            id=t["id"],
            state=TripState(t["state"]),
            start=t["start"],
            end=t.get("end"),
            duration_s=t.get("duration_s"),
            duration_min=t.get("duration_min"),
            distance_mi=t.get("distance_mi"),
            avg_speed_mph=t.get("avg_speed_mph"),
            max_speed_mph=t.get("max_speed_mph"),
            idle_time_s=t.get("idle_time_s"),
            idle_time_min=t.get("idle_time_min"),
            fuel_used_pct=t.get("fuel_used_pct"),
            fuel_estimate_status=FuelEstimateStatus(
                t.get("fuel_estimate_status") or "unavailable"
            ),
            efficiency_score=t.get("efficiency_score"),
            efficiency_confidence=t.get("efficiency_confidence"),
            efficiency_status=EfficiencyStatus(
                t.get("efficiency_status") or "withheld"
            ),
            incomplete=bool(t.get("incomplete")),
            simulated=bool(t.get("simulated", True)),
            source=t.get("source") or "simulator",
            title=t.get("title"),
            note=t.get("note"),
            revision=t.get("revision"),
        )
        dest.repo.upsert_trip_summary(summary)
        dest.repo.upsert_trip_summary(summary)

    restored = {t["id"]: t for t in dest.list_trips()}
    assert set(restored) == {a["id"], b["id"]}
    assert restored[a["id"]]["distance_mi"] == a["distance_mi"]

    buf = io.StringIO()
    fields = [
        "id",
        "state",
        "start",
        "end",
        "distance_mi",
        "duration_s",
        "revision",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for t in trips_payload:
        writer.writerow({k: t.get(k) for k in fields})
    buf.seek(0)
    rows = list(csv.DictReader(buf))
    assert {r["id"] for r in rows} == {a["id"], b["id"]}
    other.close()
