"""Voice intent routing, follow-ups, briefing, and auth-or-local gate."""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.storage import Database
from backend.voice.context import SessionContext
from backend.voice.intents import resolve_command, route_text
from backend.voice.service import VoiceService
from simulator import SimulatorProvider


@pytest.fixture
def app():
    return create_app(SimulatorProvider(), db=Database())


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


# --- pure routing ---


@pytest.mark.parametrize(
    "text,expected",
    [
        ("How much fuel is left?", "fuel_level"),
        ("what's my gas", "fuel_level"),
        ("How far will that get me?", "range_estimate"),
        ("estimated range", "range_estimate"),
        ("How was my last trip?", "last_trip"),
        ("Why is my check-engine light on?", "check_engine"),
        ("check engine", "check_engine"),
        ("Navigate home", "navigate_home"),
        ("take me home", "navigate_home"),
        ("Pause Spotify", "pause_spotify"),
        ("that's all", "end_session"),
        ("Thats all", "end_session"),
    ],
)
def test_route_text_supported(text, expected):
    intent, note = route_text(text)
    assert intent == expected
    assert note == "pattern"


def test_route_unknown():
    intent, note = route_text("open the sunroof and floor it")
    assert intent is None
    assert note == "unknown"


def test_followup_after_fuel_maps_to_range():
    intent, note = route_text("how far will that get me?", prior_intent="fuel_level")
    assert intent == "range_estimate"
    assert "followup" in note or note == "pattern"

    intent2, note2 = route_text("and the range?", prior_intent="fuel_level")
    assert intent2 == "range_estimate"
    assert note2 == "followup_after_fuel"


def test_followup_expires_without_prior():
    # Without prior context, short "the range?" still matches range pattern via "range"
    intent, _ = route_text("the range?")
    assert intent == "range_estimate"


def test_resolve_explicit_and_text():
    intent, note, text = resolve_command(intent="fuel_level")
    assert intent == "fuel_level" and note == "explicit"

    intent2, note2, _ = resolve_command(text="Pause Spotify")
    assert intent2 == "pause_spotify" and note2 == "pattern"

    bad, note3, _ = resolve_command(intent="self_destruct")
    assert bad is None and note3 == "unsupported_intent"


def test_session_context_timeout():
    ctx = SessionContext(timeout_s=0.05)
    snap = ctx.remember("fuel_level", "Fuel is about 50 percent.")
    assert snap.active
    assert ctx.prior_intent() == "fuel_level"
    time.sleep(0.08)
    assert ctx.prior_intent() is None
    assert ctx.snapshot().active is False


def test_thats_all_ends_session():
    svc = VoiceService()
    r1 = svc.handle(text="How much fuel is left?")
    # Without telemetry, fuel unavailable but session still opens on success
    assert r1["ok"] is True
    assert svc.session.prior_intent() == "fuel_level"
    r2 = svc.handle(text="that's all")
    assert r2["ok"] is True
    assert r2["intent"] == "end_session"
    assert svc.session.prior_intent() is None


# --- API ---


def test_voice_unknown_intent(client):
    r = client.post("/api/voice/command", json={"intent": "self_destruct"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["shell_executed"] is False


def test_voice_text_routing_fuel(client):
    time.sleep(0.35)
    r = client.post(
        "/api/voice/command",
        json={"text": "How much fuel is left?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["intent"] == "fuel_level"
    assert body["shell_executed"] is False
    assert "Fuel" in body["reply"] or "unavailable" in body["reply"].lower()
    assert body["auth"]["local"] is True


def test_voice_followup_api(client):
    time.sleep(0.35)
    first = client.post(
        "/api/voice/command",
        json={"text": "How much fuel is left?"},
    ).json()
    assert first["ok"] is True
    assert first["session"]["active"] is True

    second = client.post(
        "/api/voice/command",
        json={"text": "how far will that get me?"},
    ).json()
    assert second["ok"] is True
    assert second["intent"] == "range_estimate"
    assert second["prior_intent"] == "fuel_level"
    # Range honestly unavailable without calibration
    assert "range" in second["reply"].lower() or "unavailable" in (
        second.get("unavailable") or []
    )


def test_voice_end_session_clears_followup(client):
    client.post("/api/voice/command", json={"text": "fuel level"})
    end = client.post("/api/voice/command", json={"text": "that's all"}).json()
    assert end["intent"] == "end_session"
    assert end["session"]["active"] is False


def test_voice_check_engine_and_stubs(client):
    client.post("/api/simulator/scenario", json={"scenario": "check_engine"})
    time.sleep(0.4)
    cel = client.post(
        "/api/voice/command",
        json={"text": "Why is my check-engine light on?"},
    ).json()
    assert cel["ok"] is True
    assert cel["intent"] == "check_engine"
    assert "P0420" in cel["reply"] or "code" in cel["reply"].lower()

    nav = client.post(
        "/api/voice/command",
        json={"text": "Navigate home"},
    ).json()
    assert nav["intent"] == "navigate_home"
    assert nav["action"]["type"] == "deep_link_stub"
    assert nav["action"]["launched"] is False

    spot = client.post(
        "/api/voice/command",
        json={"text": "Pause Spotify"},
    ).json()
    assert spot["intent"] == "pause_spotify"
    assert spot["action"]["executed"] is False
    assert "Siri" in spot["reply"] or "Spotify" in spot["reply"]


def test_startup_briefing(client):
    time.sleep(0.35)
    r = client.get("/api/voice/briefing")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["includes_previous_trip_fuel_cost"] is False
    assert "fuel" in body["spoken"].lower() or "unavailable" in body["spoken"].lower()
    assert "previous-trip fuel cost" not in body["spoken"].lower()
    assert "audio feasibility" in body["note"].lower() or "unproven" in body["note"].lower()


def test_voice_session_endpoint(client):
    r = client.get("/api/voice/session")
    assert r.status_code == 200
    body = r.json()
    assert body["audio_feasibility_gate"] == "open"
    assert "fuel_level" in body["supported_intents"]
    assert body["followup_timeout_s"] == 15


def test_voice_requires_intent_or_text(client):
    r = client.post("/api/voice/command", json={})
    assert r.status_code == 422


def test_voice_bearer_token_when_set(client, monkeypatch):
    monkeypatch.setenv("ACCORDOS_VOICE_TOKEN", "test-voice-secret")
    # Local TestClient is still allowed without token
    ok = client.post("/api/voice/command", json={"intent": "end_session"})
    assert ok.status_code == 200

    # Simulate non-local by patching dependency path via Request client —
    # TestClient always appears local; verify token acceptance separately.
    from backend.voice import auth as voice_auth

    assert voice_auth.voice_token() == "test-voice-secret"

    class FakeClient:
        host = "192.168.1.50"

    class FakeRequest:
        client = FakeClient()

    with pytest.raises(Exception) as missing:
        voice_auth.require_voice_access(FakeRequest(), authorization=None)
    assert missing.value.status_code == 401

    allowed = voice_auth.require_voice_access(
        FakeRequest(),
        authorization="Bearer test-voice-secret",
    )
    assert allowed["auth"] == "bearer"

    with pytest.raises(Exception) as bad:
        voice_auth.require_voice_access(
            FakeRequest(),
            authorization="Bearer wrong",
        )
    assert bad.value.status_code == 403


def test_status_reports_voice(client):
    body = client.get("/api/status").json()
    assert body["api_version"] == "0.5.0"
    assert body["voice"]["audio_feasibility_gate"] == "open"
    assert body["voice"]["llm"] is False
    assert body["voice"]["wake_word"] is False


def test_no_shell_keys_in_response(client):
    r = client.post(
        "/api/voice/command",
        json={"text": "rm -rf / ; Pause Spotify"},
    ).json()
    # May route to pause_spotify because of pattern, or unknown — either way no shell
    assert r["shell_executed"] is False
    assert "action" not in r or r.get("action", {}).get("type") != "shell"
