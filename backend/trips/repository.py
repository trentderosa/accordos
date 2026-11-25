"""SQLite persistence for trips, samples, and checkpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from backend.storage import Database
from backend.telemetry.models import TelemetrySample

from .models import (
    EfficiencyStatus,
    FuelEstimateStatus,
    TripState,
    TripSummary,
)
from .state_machine import OpenTrip


def _iso(ts: datetime) -> str:
    return ts.isoformat()


class TripRepository:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.db.connect()

    def upsert_open_trip(self, trip: OpenTrip) -> None:
        conn = self.db.connect()
        now = _iso(trip.last_ts or trip.start_ts)
        conn.execute(
            """
            INSERT INTO trips (
                id, state, start_ts, end_ts, duration_s, distance_mi,
                avg_speed_mph, max_speed_mph, idle_time_s,
                fuel_start_pct, fuel_end_pct, fuel_used_pct, fuel_estimate_status,
                efficiency_score, efficiency_confidence, efficiency_status,
                efficiency_detail, incomplete, simulated, source, title, note,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, NULL, NULL, ?, NULL, ?, ?,
                ?, ?, NULL, 'unavailable',
                NULL, NULL, 'withheld', NULL, ?, ?, ?, NULL, ?,
                ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                state=excluded.state,
                distance_mi=excluded.distance_mi,
                max_speed_mph=excluded.max_speed_mph,
                idle_time_s=excluded.idle_time_s,
                fuel_start_pct=excluded.fuel_start_pct,
                fuel_end_pct=excluded.fuel_end_pct,
                incomplete=excluded.incomplete,
                note=excluded.note,
                updated_at=excluded.updated_at
            """,
            (
                trip.id,
                trip.state.value,
                _iso(trip.start_ts),
                round(trip.distance_mi, 4),
                round(trip.max_speed_mph, 2),
                round(trip.idle_time_s, 2),
                trip.fuel_start_pct,
                trip.fuel_end_pct,
                1 if trip.incomplete else 0,
                1 if trip.simulated else 0,
                trip.source,
                trip.note,
                now,
                now,
            ),
        )
        conn.commit()

    def finalize_trip(
        self,
        trip: OpenTrip,
        *,
        fuel_used_pct: Optional[float],
        fuel_status: FuelEstimateStatus,
        avg_speed: Optional[float],
        duration_s: float,
        efficiency_score: Optional[float],
        efficiency_confidence: Optional[float],
        efficiency_status: EfficiencyStatus,
        efficiency_detail: Optional[dict[str, Any]],
        title: str,
    ) -> TripSummary:
        conn = self.db.connect()
        end_ts = trip.end_ts or trip.last_ts or trip.start_ts
        detail_json = json.dumps(efficiency_detail) if efficiency_detail else None
        conn.execute(
            """
            INSERT INTO trips (
                id, state, start_ts, end_ts, duration_s, distance_mi,
                avg_speed_mph, max_speed_mph, idle_time_s,
                fuel_start_pct, fuel_end_pct, fuel_used_pct, fuel_estimate_status,
                efficiency_score, efficiency_confidence, efficiency_status,
                efficiency_detail, incomplete, simulated, source, title, note,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                state=excluded.state,
                end_ts=excluded.end_ts,
                duration_s=excluded.duration_s,
                distance_mi=excluded.distance_mi,
                avg_speed_mph=excluded.avg_speed_mph,
                max_speed_mph=excluded.max_speed_mph,
                idle_time_s=excluded.idle_time_s,
                fuel_start_pct=excluded.fuel_start_pct,
                fuel_end_pct=excluded.fuel_end_pct,
                fuel_used_pct=excluded.fuel_used_pct,
                fuel_estimate_status=excluded.fuel_estimate_status,
                efficiency_score=excluded.efficiency_score,
                efficiency_confidence=excluded.efficiency_confidence,
                efficiency_status=excluded.efficiency_status,
                efficiency_detail=excluded.efficiency_detail,
                incomplete=excluded.incomplete,
                title=excluded.title,
                note=excluded.note,
                updated_at=excluded.updated_at
            """,
            (
                trip.id,
                trip.state.value,
                _iso(trip.start_ts),
                _iso(end_ts),
                round(duration_s, 2),
                round(trip.distance_mi, 4),
                None if avg_speed is None else round(avg_speed, 2),
                round(trip.max_speed_mph, 2),
                round(trip.idle_time_s, 2),
                trip.fuel_start_pct,
                trip.fuel_end_pct,
                None if fuel_used_pct is None else round(fuel_used_pct, 3),
                fuel_status.value,
                efficiency_score,
                efficiency_confidence,
                efficiency_status.value,
                detail_json,
                1 if trip.incomplete else 0,
                1 if trip.simulated else 0,
                trip.source,
                title,
                trip.note,
                _iso(trip.start_ts),
                _iso(end_ts),
            ),
        )
        conn.commit()
        summary = self.get_trip(trip.id)
        assert summary is not None
        return summary

    def insert_sample(
        self, trip_id: str, sample: TelemetrySample, *, communicating: bool
    ) -> bool:
        """Insert a sample. Returns False if duplicate (trip_id, ts)."""
        conn = self.db.connect()
        try:
            conn.execute(
                """
                INSERT INTO trip_samples (
                    trip_id, ts, speed_mph, rpm, fuel_level_pct, coolant_c,
                    engine_load_pct, voltage_v, quality, mode, communicating
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip_id,
                    _iso(sample.timestamp),
                    sample.speed_mph,
                    sample.rpm,
                    sample.fuel_level_pct,
                    sample.coolant_c,
                    sample.engine_load_pct,
                    sample.voltage_v,
                    sample.quality,
                    sample.mode.value if sample.mode else None,
                    1 if communicating else 0,
                ),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def insert_checkpoint(self, trip: OpenTrip) -> None:
        conn = self.db.connect()
        ts = trip.last_ts or trip.start_ts
        conn.execute(
            """
            INSERT OR REPLACE INTO trip_checkpoints (
                trip_id, seq, ts, state, distance_mi, max_speed_mph,
                idle_time_s, sample_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip.id,
                trip.checkpoint_seq,
                _iso(ts),
                trip.state.value,
                round(trip.distance_mi, 4),
                round(trip.max_speed_mph, 2),
                round(trip.idle_time_s, 2),
                trip.sample_count,
            ),
        )
        conn.commit()

    def list_incomplete_trip_ids(self) -> list[str]:
        conn = self.db.connect()
        rows = conn.execute(
            """
            SELECT id FROM trips
            WHERE state IN ('starting', 'active', 'ending')
            ORDER BY start_ts
            """
        ).fetchall()
        return [r["id"] for r in rows]

    def load_open_snapshot(self, trip_id: str) -> Optional[dict[str, Any]]:
        conn = self.db.connect()
        row = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        if row is None:
            return None
        ck = conn.execute(
            """
            SELECT * FROM trip_checkpoints
            WHERE trip_id=? ORDER BY seq DESC LIMIT 1
            """,
            (trip_id,),
        ).fetchone()
        return {"trip": dict(row), "checkpoint": dict(ck) if ck else None}

    def mark_recovered_from_row(
        self, trip_id: str, *, note: str
    ) -> Optional[TripSummary]:
        conn = self.db.connect()
        row = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        if row is None:
            return None
        end_ts = row["updated_at"] or row["start_ts"]
        start_dt = datetime.fromisoformat(row["start_ts"])
        end = datetime.fromisoformat(end_ts)
        duration_s = max(0.0, (end - start_dt).total_seconds())
        distance = row["distance_mi"] or 0.0
        avg = None
        if duration_s > 0 and distance:
            avg = (distance / duration_s) * 3600.0
        title = (
            f"Recovered trip · {start_dt.astimezone(timezone.utc).strftime('%b %d · %H:%M UTC')}"
        )
        conn.execute(
            """
            UPDATE trips SET
                state='recovered',
                end_ts=?,
                duration_s=?,
                avg_speed_mph=?,
                incomplete=1,
                title=?,
                note=?,
                efficiency_status='withheld',
                efficiency_detail=?,
                updated_at=?
            WHERE id=?
            """,
            (
                end_ts,
                round(duration_s, 2),
                None if avg is None else round(avg, 2),
                title,
                note,
                json.dumps(
                    {
                        "explanation": (
                            "Efficiency withheld for recovered incomplete trip. "
                            "Not a safety assessment."
                        )
                    }
                ),
                end_ts,
                trip_id,
            ),
        )
        conn.commit()
        return self.get_trip(trip_id)

    def list_trips(self, *, limit: int = 50) -> list[TripSummary]:
        conn = self.db.connect()
        rows = conn.execute(
            """
            SELECT * FROM trips
            WHERE state IN ('finalized', 'recovered')
            ORDER BY start_ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._row_to_summary(dict(r)) for r in rows]

    def get_trip(self, trip_id: str) -> Optional[TripSummary]:
        conn = self.db.connect()
        row = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_summary(dict(row))

    def trip_exists(self, trip_id: str) -> bool:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT 1 FROM trips WHERE id=? LIMIT 1", (trip_id,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _row_to_summary(row: dict[str, Any]) -> TripSummary:
        duration_s = row.get("duration_s")
        idle_s = row.get("idle_time_s")
        detail = row.get("efficiency_detail")
        if isinstance(detail, str) and detail:
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                detail = {"raw": detail}
        else:
            detail = None

        state = TripState(row["state"])
        return TripSummary(
            id=row["id"],
            state=state,
            start=row["start_ts"],
            end=row.get("end_ts"),
            duration_s=duration_s,
            duration_min=None if duration_s is None else round(duration_s / 60.0, 1),
            distance_mi=row.get("distance_mi"),
            avg_speed_mph=row.get("avg_speed_mph"),
            max_speed_mph=row.get("max_speed_mph"),
            idle_time_s=idle_s,
            idle_time_min=None if idle_s is None else round(idle_s / 60.0, 2),
            fuel_used_pct=row.get("fuel_used_pct"),
            fuel_estimate_status=FuelEstimateStatus(
                row.get("fuel_estimate_status") or "unavailable"
            ),
            efficiency_score=row.get("efficiency_score"),
            efficiency_confidence=row.get("efficiency_confidence"),
            efficiency_status=EfficiencyStatus(
                row.get("efficiency_status") or "withheld"
            ),
            efficiency_detail=detail,
            incomplete=bool(row.get("incomplete")),
            simulated=bool(row.get("simulated", 1)),
            source=row.get("source") or "simulator",
            title=row.get("title"),
            note=row.get("note"),
            label="SIMULATED" if row.get("simulated", 1) else "LIVE",
            status=state.value,
        )
