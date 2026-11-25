"""Deterministic voice intent stub — supported intents only, no shell execution."""

from __future__ import annotations

from typing import Any

SUPPORTED = frozenset(
    {
        "fuel_level",
        "range_estimate",
        "last_trip",
        "check_engine",
        "navigate_home",
        "pause_spotify",
        "end_session",
    }
)


class VoiceService:
    def handle(self, intent: str, text: str | None = None) -> dict[str, Any]:
        intent = (intent or "").strip().lower()
        if intent not in SUPPORTED:
            return {
                "ok": False,
                "intent": intent,
                "reply": "I don't support that yet.",
                "note": "Phase 1 stub — offline voice arrives in Phase 4",
            }
        replies = {
            "fuel_level": "Fuel level is simulated in Phase 1.",
            "range_estimate": "Range estimates need calibrated fuel data.",
            "last_trip": "Trip history arrives in Phase 3.",
            "check_engine": "No diagnostic codes in the simulator. Factory warnings stay authoritative.",
            "navigate_home": "Navigation deep links arrive in Phase 5.",
            "pause_spotify": "Spotify control arrives in Phase 5.",
            "end_session": "Okay.",
        }
        return {"ok": True, "intent": intent, "reply": replies[intent], "text": text}
