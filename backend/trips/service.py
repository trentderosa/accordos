"""In-memory trip stubs for Phase 1 API surface."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


class TripService:
    def __init__(self) -> None:
        self._trips: list[dict[str, Any]] = []

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
        }
        self._trips.append(trip)
        return trip
