"""Unit tests for the OBD stub provider and env factory."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Database
from backend.telemetry.factory import build_provider, normalize_provider_name
from backend.telemetry.obd import ADAPTER_NOT_CONNECTED, ObdProvider
from simulator import SimulatorProvider


def test_normalize_provider_name():
    assert normalize_provider_name(None) == "simulator"
    assert normalize_provider_name("SIMULATOR") == "simulator"
    assert normalize_provider_name("sim") == "simulator"
    assert normalize_provider_name("OBD") == "obd"
    assert normalize_provider_name("obd-ii") == "obd"
    with pytest.raises(ValueError):
        normalize_provider_name("canbus")


def test_build_provider_from_env():
    assert isinstance(build_provider(env={"ACCORDOS_PROVIDER": "SIMULATOR"}), SimulatorProvider)
    assert isinstance(build_provider(env={"ACCORDOS_PROVIDER": "OBD"}), ObdProvider)
    assert isinstance(build_provider("obd"), ObdProvider)


def test_obd_stub_not_connected_and_unavailable():
    p = ObdProvider()

    async def _run():
        await p.connect()
        assert p.is_connected() is False
        caps = await p.discover_capabilities()
        sample = await p.read()
        await p.disconnect()
        return caps, sample

    caps, sample = asyncio.run(_run())
    assert caps["provider"] == "obd"
    assert caps["read_only"] is True
    assert caps["can_clear_codes"] is False
    assert caps["can_write"] is False
    assert caps["adapter_connected"] is False
    assert caps["metrics"] == []
    assert "rpm" in caps["unavailable_metrics"]
    assert caps["pid_status"]["010C"] == "unavailable"
    assert sample.quality == "unavailable"
    assert sample.simulated is False
    assert sample.source == "obd"
    assert ADAPTER_NOT_CONNECTED in (sample.message or "")
    assert p.read_dtcs() == []


def test_obd_capabilities_sync_matches_discovery():
    p = ObdProvider()

    async def _run():
        await p.connect()
        discovered = await p.discover_capabilities()
        return discovered, p.capabilities()

    discovered, cached = asyncio.run(_run())
    assert discovered["pid_status"] == cached["pid_status"]
    assert cached["message"]


def test_api_with_obd_provider():
    app = create_app(ObdProvider(), db=Database())
    with TestClient(app) as client:
        root = client.get("/").json()
        assert root["provider"] == "obd"
        assert root["api_version"] == "0.6.0"
        assert "adapter not connected" in root["note"].lower()

        caps = client.get("/api/capabilities").json()
        assert caps["provider"] == "obd"
        assert caps["adapter_connected"] is False
        assert caps["metrics"] == []

        status = client.get("/api/status").json()
        assert status["connection"]["provider"] == "obd"
        assert status["connection"]["simulated"] is False
        assert status["connection"]["provider_connected"] is False

        latest = client.get("/api/telemetry/latest").json()
        assert latest["quality"] == "unavailable"
        assert latest.get("simulated") is False
        assert ADAPTER_NOT_CONNECTED in (latest.get("message") or "")

        # Scenario controls require simulator
        r = client.post(
            "/api/simulator/scenario",
            json={"scenario": "idle"},
        )
        assert r.status_code == 400
