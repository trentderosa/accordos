"""Integration tests for REST stubs and WebSocket telemetry."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from simulator import SimulatorProvider


@pytest.fixture
def app():
    return create_app(SimulatorProvider())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "AccordOS"
    assert body["phase"] == 1
    assert "SIMULATED" in body["note"]


def test_capabilities(client):
    r = client.get("/api/capabilities")
    assert r.status_code == 200
    assert r.json()["simulated"] is True


def test_status(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert body["connection"]["provider"] == "simulator"
    assert body["connection"]["simulated"] is True


def test_telemetry_latest_simulated(client):
    # Allow poll loop to produce a sample
    import time

    time.sleep(0.4)
    r = client.get("/api/telemetry/latest")
    assert r.status_code == 200
    body = r.json()
    assert body.get("label") == "SIMULATED" or body.get("simulated") is True


def test_health_and_maintenance_stubs(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/maintenance").status_code == 200
    assert client.get("/api/trips").json()["simulated"] is True
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
    app = create_app(SimulatorProvider())
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            msg = ws.receive_json()
            assert msg.get("simulated") is True or msg.get("label") == "SIMULATED"



def test_storage_schema_version():
    from backend.storage import Database

    db = Database()
    assert db.schema_version() == 0
    db.close()
