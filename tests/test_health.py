"""Health core: DTCs, reference explanations, trends, maintenance."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend.health.reference import explain_code
from backend.health.thresholds import COOLANT, next_status
from backend.main import create_app
from backend.storage import Database
from simulator import SimulatorProvider


@pytest.fixture
def app():
    return create_app(SimulatorProvider(), db=Database())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_explain_code_is_not_a_diagnosis():
    expl = explain_code("P0420")
    assert expl["reference_found"] is True
    assert expl["interpretation"] == "code"
    assert "not a confirmed diagnosis" in expl["interpretation_note"].lower()
    assert expl["code"] == "P0420"


def test_explain_unknown_code():
    expl = explain_code("U9999")
    assert expl["reference_found"] is False
    assert expl["interpretation"] == "code"


def test_coolant_hysteresis():
    assert next_status(COOLANT, 101.0, "ok") == "watch"
    assert next_status(COOLANT, 110.0, "watch") == "alert"
    # Still alert until clear_alert
    assert next_status(COOLANT, 105.0, "alert") == "alert"
    assert next_status(COOLANT, 100.0, "alert") == "watch"
    assert next_status(COOLANT, 90.0, "watch") == "ok"


def test_schema_version_includes_health(client):
    db = Database()
    assert db.schema_version() == 3
    db.close()
    status = client.get("/api/status").json()
    assert status["phase"] == 5
    assert status["api_version"] == "0.5.0"
    assert status["health"]["can_clear_codes"] is False
    assert status["trip"]["schema_version"] == 3


def test_health_and_maintenance_sqlite_backed(client):
    time.sleep(0.5)
    health = client.get("/api/health").json()
    assert health["read_only"] is True
    assert health["can_clear_codes"] is False
    assert health["simulated"] is True
    assert "not confirmed" in health["disclaimer"].lower() or "not a confirmed" in health[
        "disclaimer"
    ].lower()
    assert isinstance(health["dtcs"], list)
    assert isinstance(health["trends"], list)
    assert isinstance(health["alerts"], list)

    maint = client.get("/api/maintenance").json()
    assert maint["simulated"] is True
    assert len(maint["reminders"]) >= 1
    assert all(r.get("simulated") for r in maint["reminders"])
    assert "odometer" in maint["note"].lower()


def test_check_engine_scenario_reports_p0420(client):
    r = client.post("/api/simulator/scenario", json={"scenario": "check_engine"})
    assert r.status_code == 200
    time.sleep(0.6)
    health = client.get("/api/health").json()
    active = [d for d in health["dtcs"] if d["status"] == "active"]
    codes = {d["code"] for d in active}
    assert "P0420" in codes
    p0420 = next(d for d in active if d["code"] == "P0420")
    assert p0420["interpretation"] == "code"
    assert "diagnosis" in p0420["interpretation_note"].lower()
    assert health["can_clear_codes"] is False


def test_misfire_scenario_multiple_codes(client):
    client.post("/api/simulator/scenario", json={"scenario": "misfire"})
    time.sleep(0.6)
    health = client.get("/api/health").json()
    active = {d["code"] for d in health["dtcs"] if d["status"] == "active"}
    assert "P0300" in active
    assert "P0171" in active


def test_healthy_scenario_no_active_dtcs(client):
    client.post("/api/simulator/scenario", json={"scenario": "check_engine"})
    time.sleep(0.4)
    client.post("/api/simulator/scenario", json={"scenario": "healthy"})
    time.sleep(0.6)
    health = client.get("/api/health").json()
    active = [d for d in health["dtcs"] if d["status"] == "active"]
    assert active == []
    # History retained — never cleared from ECU by us
    historical = [d for d in health["dtcs"] if d["status"] == "historical"]
    assert any(d["code"] == "P0420" for d in historical)


def test_overheat_raises_coolant_trend(client):
    client.post("/api/simulator/scenario", json={"scenario": "overheat"})
    # Force enough samples past the downsample interval
    time.sleep(5.5)
    health = client.get("/api/health").json()
    coolant = next(t for t in health["trends"] if t["metric"] == "coolant_c")
    assert coolant["latest"] is not None
    assert coolant["latest"] >= 100.0
    assert coolant["status"] in ("watch", "alert")


def test_low_voltage_trend(client):
    client.post("/api/simulator/scenario", json={"scenario": "low_voltage"})
    time.sleep(5.5)
    health = client.get("/api/health").json()
    voltage = next(t for t in health["trends"] if t["metric"] == "voltage_v")
    assert voltage["latest"] is not None
    assert voltage["latest"] <= 12.2
    assert voltage["status"] in ("watch", "alert")


def test_no_clear_endpoint_exists(client):
    # Defensive: clearing must not be offered
    assert client.delete("/api/health/dtcs").status_code in (404, 405, 422)
    assert client.post("/api/health/clear").status_code in (404, 405, 422)


def test_root_phase_note(client):
    body = client.get("/").json()
    assert body["phase"] == 5
    assert body["api_version"] == "0.5.0"
    assert "health" in body["phase_note"].lower()
    assert "voice" in body["phase_note"].lower()
