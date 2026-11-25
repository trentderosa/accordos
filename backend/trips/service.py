"""In-memory trip stubs for Phase 1 API surface."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4


class TripService:
    def __init__(self, *, seed_placeholders: bool = True) -> None:
        self._trips: list[dict[str, Any]] = []
        if seed_placeholders:
            self._seed_placeholders()

    def list_trips(self) -> list[dict[str, Any]]:
        return list(self._trips)

    def get_trip(self, trip_id: str) -> Optional[dict[str, Any]]:
        for t in self._trips:
            if t["id"] == trip_id:
                return t
        return None

    def sync(self, cursor: Optional[str] = None) -> dict[str, Any]:
        return {
            "cursor": cursor or "0",
            "next_cursor": "0",
            "revisions": [],
            "note": "Phase 1 stub — sync arrives in Phase 3",
        }

    def seed_demo(self) -> dict[str, Any]:
        """Optional demo trip for UI scaffolding (clearly simulated)."""
        trip = {
            "id": str(uuid4()),
            "start": datetime.now(timezone.utc).isoformat(),
            "end": None,
            "distance_mi": None,
            "avg_speed_mph": None,
            "max_speed_mph": None,
            "simulated": True,
            "status": "stub",
            "label": "SIMULATED",
        }
        self._trips.append(trip)
        return trip

    def _seed_placeholders(self) -> None:
        """Static placeholder history for parked-mode demos — not real drives."""
        now = datetime.now(timezone.utc)
        self._trips = [
            {
                "id": "sim-trip-placeholder-1",
                "title": "Campus → Apt",
                "start": (now - timedelta(hours=26)).isoformat(),
                "end": (now - timedelta(hours=25, minutes=42)).isoformat(),
                "distance_mi": 4.2,
                "avg_speed_mph": 18.0,
                "max_speed_mph": 37.0,
                "duration_min": 18,
                "simulated": True,
                "status": "placeholder",
                "label": "SIMULATED",
                "note": "Placeholder — real trip journal arrives in Phase 3",
            },
            {
                "id": "sim-trip-placeholder-2",
                "title": "Errand loop",
                "start": (now - timedelta(days=3, hours=2)).isoformat(),
                "end": (now - timedelta(days=3, hours=1, minutes=35)).isoformat(),
                "distance_mi": 6.8,
                "avg_speed_mph": 22.0,
                "max_speed_mph": 41.0,
                "duration_min": 25,
                "simulated": True,
                "status": "placeholder",
                "label": "SIMULATED",
                "note": "Placeholder — real trip journal arrives in Phase 3",
            },
        ]
