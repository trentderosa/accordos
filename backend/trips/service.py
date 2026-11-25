"""Trip intelligence service — state machine + SQLite persistence."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from backend.storage import Database
from backend.telemetry.models import TelemetrySample

from .efficiency import score_trip
from .models import FuelEstimateStatus, TripState, TripSummary
from .repository import TripRepository
from .state_machine import TripStateMachine, classify_engine

logger = logging.getLogger(__name__)


def _title_for(trip_start: datetime, *, incomplete: bool, recovered: bool) -> str:
    when = trip_start.astimezone(timezone.utc).strftime("%b %d · %H:%M UTC")
    if recovered:
        return f"Recovered trip · {when}"
    if incomplete:
        return f"Incomplete trip · {when}"
    return f"Trip · {when}"


class TripService:
    """Authoritative trip journal backed by SQLite.

    Call ``ingest(sample)`` from the telemetry poll loop. Interrupted trips are
    recovered on construction.
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        seed_placeholders: bool = False,
        recover_on_start: bool = True,
    ) -> None:
        self.db = db or Database()
        self.db.connect()
        self.repo = TripRepository(self.db)
        self.machine = TripStateMachine()
        self._lock = threading.RLock()
        self._current_api: Optional[dict[str, Any]] = None
        if recover_on_start:
            self.recover_interrupted()
        if seed_placeholders:
            # Kept for backward-compatible tests; prefer real trips.
            self._seed_placeholders()

    def list_trips(self) -> list[dict[str, Any]]:
        with self._lock:
            trips = [t.to_api() for t in self.repo.list_trips()]
            # Include in-progress trip at the front when present
            if self._current_api and self.machine.open is not None:
                trips = [self._current_api, *trips]
            return trips

    def get_trip(self, trip_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            if self._current_api and self._current_api.get("id") == trip_id:
                return self._current_api
            trip = self.repo.get_trip(trip_id)
            return trip.to_api() if trip else None

    def sync(
        self, cursor: Optional[str] = None, *, limit: int = 50
    ) -> dict[str, Any]:
        """Pi-authoritative incremental sync of completed trips.

        Cursor is the last applied integer ``revision`` (string form). Use ``0``
        or omit to pull from the beginning. Each revision is an idempotent
        upsert keyed by stable trip ``id`` — replaying the same page is safe.
        Open/in-progress trips are not included; only finalized/recovered.
        """
        page_size = max(1, min(int(limit), 200))
        after = 0
        if cursor is not None and str(cursor).strip() not in ("", "0"):
            try:
                after = int(str(cursor).strip())
            except ValueError as exc:
                raise ValueError(
                    "sync cursor must be an integer revision string"
                ) from exc
            if after < 0:
                raise ValueError("sync cursor must be >= 0")

        with self._lock:
            window_plus = self.repo.list_sync_trips_after(
                after, limit=page_size + 1
            )
            has_more = len(window_plus) > page_size
            window = window_plus[:page_size]
            next_cursor = (
                str(window[-1].revision)
                if window and window[-1].revision is not None
                else str(after)
            )
            return {
                "cursor": str(after),
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": page_size,
                "revisions": [
                    {
                        "revision": t.revision,
                        "op": "upsert",
                        "entity": "trip",
                        "id": t.id,
                        "trip": t.to_api(),
                    }
                    for t in window
                ],
                "semantics": {
                    "authoritative": "pi",
                    "stable_ids": True,
                    "idempotent_upserts": True,
                    "cursor_field": "revision",
                    "apply": (
                        "Upsert each revision.trip by trip.id. Re-fetching the "
                        "same cursor returns the same page and may be replayed."
                    ),
                    "offline": (
                        "Phone replica may serve Recent Trips after a prior sync "
                        "when the Pi is unreachable. Background PWA sync is not promised."
                    ),
                },
                "note": "Pi remains authoritative — phone holds an IndexedDB replica",
            }

    def recover_interrupted(self) -> list[dict[str, Any]]:
        """Mark any non-finalized DB trips as recovered (power-loss path)."""
        recovered: list[dict[str, Any]] = []
        with self._lock:
            for trip_id in self.repo.list_incomplete_trip_ids():
                summary = self.repo.mark_recovered_from_row(
                    trip_id,
                    note="Interrupted trip recovered after shutdown",
                )
                if summary:
                    recovered.append(summary.to_api())
                    logger.info("Recovered interrupted trip %s", trip_id)
            # Also clear any in-memory open trip (tests / re-entrant)
            forced = self.machine.force_recover_open()
            if forced is not None:
                summary = self._persist_closed(forced)
                recovered.append(summary.to_api())
        return recovered

    def ingest(self, sample: TelemetrySample) -> Optional[dict[str, Any]]:
        """Feed one telemetry sample into the trip state machine."""
        with self._lock:
            result = self.machine.ingest(sample)
            evidence = classify_engine(sample)

            if result.opened and result.trip is not None:
                self.repo.upsert_open_trip(result.trip)
                self.repo.insert_sample(
                    result.trip.id, sample, communicating=evidence.communicating
                )
                self._refresh_current(result.trip)
                logger.info("Trip started %s", result.trip.id)

            elif result.sample_recorded and result.trip is not None and not result.closed:
                self.repo.upsert_open_trip(result.trip)
                self.repo.insert_sample(
                    result.trip.id, sample, communicating=evidence.communicating
                )
                if result.checkpoint_due:
                    self.machine.mark_checkpoint(sample.timestamp)
                    self.repo.insert_checkpoint(result.trip)
                self._refresh_current(result.trip)

            if result.closed and result.trip is not None:
                # Ensure last sample stored before finalize
                self.repo.insert_sample(
                    result.trip.id, sample, communicating=evidence.communicating
                )
                summary = self._persist_closed(result.trip)
                self._current_api = None
                logger.info(
                    "Trip %s → %s (%.2f mi)",
                    summary.id,
                    summary.state.value,
                    summary.distance_mi or 0.0,
                )
                return summary.to_api()

            return self._current_api

    def simulate_shutdown(self) -> list[dict[str, Any]]:
        """Test helper: checkpoint open trip and recover as if power was lost."""
        with self._lock:
            if self.machine.open is not None:
                self.repo.upsert_open_trip(self.machine.open)
                self.machine.mark_checkpoint()
                self.repo.insert_checkpoint(self.machine.open)
                # Leave row in active/starting/ending — clear memory
                self.machine.open = None
                self.machine.state = TripState.IDLE
                self._current_api = None
        return self.recover_interrupted()

    def current_trip(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._current_api

    def seed_demo(self) -> dict[str, Any]:
        """Optional demo finalized trip for UI scaffolding."""
        now = datetime.now(timezone.utc)
        trip_id = str(uuid4())
        from .state_machine import OpenTrip

        open_trip = OpenTrip(
            id=trip_id,
            state=TripState.FINALIZED,
            start_ts=now,
            end_ts=now,
            distance_mi=1.2,
            max_speed_mph=35.0,
            idle_time_s=20.0,
            moving_time_s=180.0,
            speed_time_integral=35.0 * 180.0,
            sample_count=40,
            simulated=True,
            source="simulator",
        )
        summary = self._persist_closed(open_trip)
        return summary.to_api()

    def _persist_closed(self, trip) -> TripSummary:
        end = trip.end_ts or trip.last_ts or trip.start_ts
        duration_s = max(0.0, (end - trip.start_ts).total_seconds())
        avg = None
        if trip.moving_time_s > 0:
            avg = trip.speed_time_integral / trip.moving_time_s
        elif duration_s > 0 and trip.distance_mi > 0:
            avg = (trip.distance_mi / duration_s) * 3600.0

        fuel_used = None
        fuel_status = FuelEstimateStatus.UNAVAILABLE
        if trip.fuel_start_pct is not None and trip.fuel_end_pct is not None:
            delta = trip.fuel_start_pct - trip.fuel_end_pct
            if trip.distance_mi < 0.25:
                fuel_status = FuelEstimateStatus.INSUFFICIENT
            elif delta < 0:
                # Refuel mid-trip or noisy sensor — do not invent consumption
                fuel_status = FuelEstimateStatus.INSUFFICIENT
            elif delta < 0.05:
                fuel_status = FuelEstimateStatus.INSUFFICIENT
            else:
                fuel_used = delta
                fuel_status = FuelEstimateStatus.AVAILABLE
        else:
            fuel_status = FuelEstimateStatus.UNAVAILABLE

        efficiency = score_trip(trip)
        title = _title_for(
            trip.start_ts,
            incomplete=trip.incomplete,
            recovered=trip.state == TripState.RECOVERED,
        )
        return self.repo.finalize_trip(
            trip,
            fuel_used_pct=fuel_used,
            fuel_status=fuel_status,
            avg_speed=avg,
            duration_s=duration_s,
            efficiency_score=efficiency.score
            if efficiency.status.value == "available"
            else None,
            efficiency_confidence=efficiency.confidence,
            efficiency_status=efficiency.status,
            efficiency_detail=efficiency.model_dump(mode="json"),
            title=title,
        )

    def _refresh_current(self, trip) -> None:
        end = trip.last_ts or trip.start_ts
        duration_s = max(0.0, (end - trip.start_ts).total_seconds())
        avg = None
        if trip.moving_time_s > 0:
            avg = trip.speed_time_integral / trip.moving_time_s
        self._current_api = {
            "id": trip.id,
            "state": trip.state.value,
            "status": trip.state.value,
            "start": trip.start_ts.isoformat(),
            "end": None,
            "duration_s": round(duration_s, 2),
            "duration_min": round(duration_s / 60.0, 1),
            "distance_mi": round(trip.distance_mi, 3),
            "avg_speed_mph": None if avg is None else round(avg, 1),
            "max_speed_mph": round(trip.max_speed_mph, 1),
            "idle_time_s": round(trip.idle_time_s, 1),
            "idle_time_min": round(trip.idle_time_s / 60.0, 2),
            "fuel_estimate_status": "unavailable",
            "efficiency_status": "withheld",
            "incomplete": trip.incomplete,
            "simulated": trip.simulated,
            "source": trip.source,
            "title": "In progress",
            "label": "SIMULATED" if trip.simulated else "LIVE",
            "note": "Trip in progress — summary finalizes when the engine stops",
        }

    def _seed_placeholders(self) -> None:
        """No-op placeholders removed in Phase 3 — real SQLite trips only."""
        return
