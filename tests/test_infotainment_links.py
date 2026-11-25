"""Link encoding tests for Waze / Apple Maps / Spotify stubs."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.infotainment.links import (
    apple_maps_directions_url,
    encode_destination,
    maps_deep_links,
    spotify_open_url,
    spotify_stub_action,
    waze_navigate_url,
)
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


def test_encode_destination_spaces_and_punctuation():
    assert encode_destination("Home") == "Home"
    assert encode_destination("  123 Main St  ") == "123+Main+St"
    assert encode_destination("Café & Bar") == "Caf%C3%A9+%26+Bar"
    assert encode_destination("a/b?c=d") == "a%2Fb%3Fc%3Dd"


def test_encode_destination_rejects_empty():
    with pytest.raises(ValueError):
        encode_destination("")
    with pytest.raises(ValueError):
        encode_destination("   ")


def test_waze_navigate_url_encodes_query():
    url = waze_navigate_url("123 Main St")
    assert url.startswith("https://waze.com/ul?")
    assert "q=123+Main+St" in url
    assert "navigate=yes" in url
    assert waze_navigate_url("Home", navigate=False).endswith("navigate=no")


def test_apple_maps_directions_url_encodes_daddr():
    url = apple_maps_directions_url("123 Main St")
    assert url.startswith("http://maps.apple.com/?")
    assert "daddr=123+Main+St" in url
    assert "dirflg=d" in url


def test_maps_deep_links_pair():
    links = maps_deep_links("Home")
    assert links["waze"] == waze_navigate_url("Home")
    assert links["apple_maps"] == apple_maps_directions_url("Home")
    # Must not invent incident/police payloads
    assert "police" not in links
    assert "incident" not in links


def test_spotify_stub_has_no_secrets():
    action = spotify_stub_action(requested="pause")
    assert action["executed"] is False
    assert action["client_secret_in_frontend"] is False
    assert action["open_url"] == spotify_open_url() == "https://open.spotify.com/"
    assert "secret" not in str(action).lower() or "client_secret_in_frontend" in action
    assert action["oauth"] == "pkce_documented_not_wired"


def test_voice_home_links_use_encoder(client):
    """Voice navigate_home returns encoded deep links from the shared helper."""
    from backend.infotainment.links import maps_deep_links

    expected = maps_deep_links("Home")
    r = client.post("/api/voice/command", json={"text": "Navigate home"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "navigate_home"
    assert body["action"]["links"]["waze"] == expected["waze"]
    assert body["action"]["links"]["apple_maps"] == expected["apple_maps"]
    assert body["action"]["launched"] is False
