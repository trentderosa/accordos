"""Phase 5 light stubs — maps deep links and Spotify open/Siri fallback.

No paid APIs. No client secrets. Core app works without these integrations.
Never fabricates live map traffic, police reports, or Spotify playback state.
"""

from .links import (
    apple_maps_directions_url,
    encode_destination,
    maps_deep_links,
    spotify_open_url,
    spotify_siri_hint,
    waze_navigate_url,
)

__all__ = [
    "apple_maps_directions_url",
    "encode_destination",
    "maps_deep_links",
    "spotify_open_url",
    "spotify_siri_hint",
    "waze_navigate_url",
]
