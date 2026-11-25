"""Deep-link builders for Waze, Apple Maps, and Spotify open stubs.

URLs only — no embedded maps, no incident feeds, no Spotify client secrets.
Destinations are percent-encoded so spaces and punctuation survive the query string.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, quote_plus


def encode_destination(destination: str) -> str:
    """Percent-encode a human destination for use in query values.

    Uses quote_plus so spaces become ``+`` (Waze/Apple Maps friendly).
    Empty or whitespace-only input raises ValueError — callers must not invent places.
    """
    cleaned = (destination or "").strip()
    if not cleaned:
        raise ValueError("destination must be a non-empty string")
    return quote_plus(cleaned, safe="")


def waze_navigate_url(destination: str, *, navigate: bool = True) -> str:
    """Build a Waze Universal Link for search/navigate.

    Docs: https://developers.google.com/waze/deeplinks
    Community reports stay in Waze — AccordOS never scrapes or fabricates them.
    """
    q = encode_destination(destination)
    nav = "yes" if navigate else "no"
    return f"https://waze.com/ul?q={q}&navigate={nav}"


def apple_maps_directions_url(destination: str, *, dirflg: str = "d") -> str:
    """Build an Apple Maps directions deep link (``daddr`` + drive flag by default).

    Uses ``http://maps.apple.com/`` scheme Apple documents for cross-platform launch.
    """
    daddr = encode_destination(destination)
    flag = quote(dirflg, safe="")
    return f"http://maps.apple.com/?daddr={daddr}&dirflg={flag}"


def maps_deep_links(destination: str) -> dict[str, str]:
    """Waze + Apple Maps URLs for the same encoded destination."""
    return {
        "waze": waze_navigate_url(destination),
        "apple_maps": apple_maps_directions_url(destination),
    }


def spotify_open_url() -> str:
    """Open the Spotify app or web player — no OAuth, no client secret.

    Core AccordOS must work without Spotify. Playback control via Web API
    requires a future OAuth PKCE flow (see docs/infotainment.md); never put
    client secrets in the frontend.
    """
    return "https://open.spotify.com/"


def spotify_siri_hint() -> str:
    """Spoken / UI hint when API control is unavailable."""
    return "Open Spotify or ask Siri — AccordOS does not control playback yet."


def spotify_stub_action(*, requested: str = "open") -> dict[str, Any]:
    """Structured stub for voice / UI — never claims playback succeeded."""
    return {
        "type": "spotify_stub",
        "requested": requested,
        "executed": False,
        "open_url": spotify_open_url(),
        "fallback": spotify_siri_hint(),
        "oauth": "pkce_documented_not_wired",
        "client_secret_in_frontend": False,
    }
