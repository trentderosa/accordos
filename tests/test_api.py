"""Integration tests for REST stubs and WebSocket telemetry."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

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


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "AccordOS"
    assert body["phase"] == 5
    assert "SIMULATED" in body["note"]
    assert "local network" in body.get("lan", "").lower()


def test_cors_allows_lan_origin(client):
    origin = "http://192.168.1.42:5173"
    r = client.options(
        "/api/status",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_public_origin(client):
    origin = "https://evil.example"
    r = client.options(
        "/api/status",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") != origin


def test_capabilities(client):
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    body = r.json()
    assert body["simulated"] is True
    assert "disconnect" in body["scenarios"]


def test_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connection"]["provider"] == "simulator"
    assert body["connection"]["simulated"] is True


def test_telemetry_latest_simulated(client):
    time.sleep(0.4)
    r = client.get("/api/telemetry/latest")
    assert r.status_code == 200
    body = r.json()
    assert body.get("label") == "SIMULATED" or body.get("simulated") is True


def test_health_and_maintenance_stubs(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/maintenance").status_code == 200
    trips = client.get("/api/trips").json()
    assert trips["simulated"] is True
    assert trips["source"] == "sqlite"
    assert isinstance(trips["trips"], list)
    assert all(t.get("simulated") for t in trips["trips"])
    assert client.get("/api/sync").status_code == 200


def test_voice_unknown_intent(client):
    r = client.post("/api/voice/command", json={"intent": "self_destruct"})
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_voice_supported_intent(client):
    r = client.post("/api/voice/command", json={"intent": "fuel_level"})
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_websocket_streams_simulated():
    app = create_app(SimulatorProvider(), db=Database())
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            msg = ws.receive_json()
            assert msg.get("simulated") is True or msg.get("label") == "SIMULATED"


def test_scenario_controls_idle_cruise_disconnect_recover(client):
    get0 = client.get("/api/simulator/scenario")
    assert get0.status_code == 200
    assert get0.json()["scenario"] == "auto"

    idle = client.post("/api/simulator/scenario", json={"scenario": "idle"})
    assert idle.status_code == 200
    assert idle.json()["scenario"] == "idle"
    time.sleep(0.35)
    sample_idle = client.get("/api/telemetry/latest").json()
    assert sample_idle.get("mode") == "unknown"
    assert sample_idle.get("speed_mph") == 0.0

    cruise = client.post("/api/simulator/scenario", json={"scenario": "cruise"})
    assert cruise.status_code == 200
    time.sleep(0.35)
    sample_cruise = client.get("/api/telemetry/latest").json()
    assert sample_cruise.get("mode") == "driving"
    assert (sample_cruise.get("speed_mph") or 0) > 40

    lost = client.post("/api/simulator/scenario", json={"scenario": "disconnect"})
    assert lost.status_code == 200
    assert lost.json()["signal_lost"] is True
    time.sleep(0.35)
    sample_lost = client.get("/api/telemetry/latest").json()
    assert sample_lost.get("quality") == "unavailable"
    assert sample_lost.get("simulated") is True

    recover = client.post("/api/simulator/scenario", json={"scenario": "recover"})
    assert recover.status_code == 200
    assert recover.json()["scenario"] == "auto"
    assert recover.json()["signal_lost"] is False
    time.sleep(0.35)
    sample_ok = client.get("/api/telemetry/latest").json()
    assert sample_ok.get("quality") == "good"


def test_scenario_parked_and_invalid(client):
    parked = client.post("/api/simulator/scenario", json={"scenario": "parked"})
    assert parked.status_code == 200
    time.sleep(0.35)
    sample = client.get("/api/telemetry/latest").json()
    assert sample.get("mode") == "parked"

    bad = client.post("/api/simulator/scenario", json={"scenario": "boost"})
    assert bad.status_code == 400


def test_storage_schema_version():
    db = Database()
    assert db.schema_version() == 3
    db.close()
