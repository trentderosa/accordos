"""SQLite persistence for diagnostics, trends, and maintenance reminders."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from backend.storage import Database

from .reference import explain_code
from .thresholds import TrendStatus


def _iso(ts: Optional[datetime] = None) -> str:
    return (ts or datetime.now(timezone.utc)).isoformat()


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


class HealthRepository:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.db.connect()

    def seed_maintenance_if_empty(self) -> None:
        conn = self.db.connect()
        count = conn.execute("SELECT COUNT(*) AS n FROM maintenance_reminders").fetchone()
        if count and int(count["n"]) > 0:
            return
        now = _iso()
        rows = [
            (
                str(uuid4()),
                "Engine oil & filter",
                "oil_change",
                "Every 5,000 mi or 6 months (owner interval)",
                5000.0,
                6,
                "Last logged: ~4,200 mi ago (simulated label)",
                "due_soon",
                "Interval is user-provided — not a live odometer reading.",
                1,
                "user_interval",
                now,
                now,
            ),
            (
                str(uuid4()),
                "Cabin air filter",
                "cabin_filter",
                "Every 15,000 mi or 12 months (owner interval)",
                15000.0,
                12,
                "Last logged: spring service (simulated label)",
                "upcoming",
                "Reminder only — confirm against records you keep.",
                1,
                "user_interval",
                now,
                now,
            ),
            (
                str(uuid4()),
                "Tire rotation",
                "tire_rotation",
                "Every 7,500 mi (owner interval)",
                7500.0,
                None,
                "Last logged: unknown",
                "unknown",
                "No fabricated mileage — status stays unknown until you set dates.",
                1,
                "user_interval",
                now,
                now,
            ),
        ]
        conn.executemany(
            """
            INSERT INTO maintenance_reminders (
                id, title, kind, due_label, interval_mi, interval_months,
                last_service_label, status, note, simulated, source,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    def upsert_active_dtcs(self, codes: list[str], *, source: str, simulated: bool) -> None:
        """Mark listed codes active; previously active codes missing become historical.

        Never deletes history and never issues clear-DTC commands.
        """
        conn = self.db.connect()
        now = _iso()
        normalized = [c.strip().upper() for c in codes if c and c.strip()]
        active_rows = conn.execute(
            "SELECT code FROM diagnostic_events WHERE status='active'"
        ).fetchall()
        previously = {row["code"] for row in active_rows}

        for code in normalized:
            expl = explain_code(code)
            existing = conn.execute(
                "SELECT id, status FROM diagnostic_events WHERE code=? ORDER BY last_seen DESC LIMIT 1",
                (code,),
            ).fetchone()
            if existing and existing["status"] == "active":
                conn.execute(
                    """
                    UPDATE diagnostic_events
                    SET last_seen=?, title=?, summary=?, explanation_json=?,
                        severity=?, system=?, source=?, simulated=?, updated_at=?
                    WHERE id=?
                    """,
                    (
                        now,
                        expl["title"],
                        expl["summary"],
                        json.dumps(expl),
                        expl["severity"],
                        expl["system"],
                        source,
                        1 if simulated else 0,
                        now,
                        existing["id"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO diagnostic_events (
                        id, code, status, title, summary, explanation_json,
                        severity, system, first_seen, last_seen, source,
                        simulated, created_at, updated_at
                    ) VALUES (?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        code,
                        expl["title"],
                        expl["summary"],
                        json.dumps(expl),
                        expl["severity"],
                        expl["system"],
                        now,
                        now,
                        source,
                        1 if simulated else 0,
                        now,
                        now,
                    ),
                )

        for code in previously - set(normalized):
            # Code no longer reported by the provider — keep history, do not "clear".
            conn.execute(
                """
                UPDATE diagnostic_events
                SET status='historical', updated_at=?,
                    note='No longer reported by provider — history retained; AccordOS never clears ECU codes'
                WHERE code=? AND status='active'
                """,
                (now, code),
            )
        conn.commit()

    def list_dtcs(self, *, include_historical: bool = True) -> list[dict[str, Any]]:
        conn = self.db.connect()
        if include_historical:
            rows = conn.execute(
                """
                SELECT * FROM diagnostic_events
                ORDER BY
                  CASE status WHEN 'active' THEN 0 ELSE 1 END,
                  last_seen DESC
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM diagnostic_events
                WHERE status='active'
                ORDER BY last_seen DESC
                """
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            expl = {}
            try:
                expl = json.loads(row["explanation_json"] or "{}")
            except json.JSONDecodeError:
                expl = explain_code(row["code"])
            out.append(
                {
                    "code": row["code"],
                    "title": row["title"] or expl.get("title", row["code"]),
                    "summary": row["summary"] or expl.get("summary", ""),
                    "common_causes": expl.get("common_causes", []),
                    "interpretation": "code",
                    "interpretation_note": expl.get(
                        "interpretation_note",
                        "This is a diagnostic trouble code, not a confirmed diagnosis.",
                    ),
                    "severity": row["severity"] or expl.get("severity", "info"),
                    "system": row["system"] or expl.get("system", "unknown"),
                    "reference_found": bool(expl.get("reference_found", True)),
                    "status": row["status"],
                    "first_seen": _parse(row["first_seen"]),
                    "last_seen": _parse(row["last_seen"]),
                    "source": row["source"],
                    "simulated": bool(row["simulated"]),
                }
            )
        return out

    def insert_trend_sample(
        self,
        metric: str,
        value: float,
        ts: Optional[datetime] = None,
    ) -> None:
        conn = self.db.connect()
        conn.execute(
            """
            INSERT INTO telemetry_trend_samples (metric, ts, value)
            VALUES (?, ?, ?)
            """,
            (metric, _iso(ts), float(value)),
        )
        # Retain a rolling window (~2 hours at 5s cadence ≈ 1440; keep 500).
        conn.execute(
            """
            DELETE FROM telemetry_trend_samples
            WHERE id NOT IN (
                SELECT id FROM telemetry_trend_samples
                WHERE metric=?
                ORDER BY ts DESC
                LIMIT 500
            ) AND metric=?
            """,
            (metric, metric),
        )
        conn.commit()

    def recent_trend_samples(
        self, metric: str, *, limit: int = 48
    ) -> list[tuple[datetime, float]]:
        conn = self.db.connect()
        rows = conn.execute(
            """
            SELECT ts, value FROM telemetry_trend_samples
            WHERE metric=?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (metric, limit),
        ).fetchall()
        points: list[tuple[datetime, float]] = []
        for row in reversed(rows):
            ts = _parse(row["ts"])
            if ts is None:
                continue
            points.append((ts, float(row["value"])))
        return points

    def get_trend_state(self, metric: str) -> TrendStatus:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT status FROM trend_state WHERE metric=?",
            (metric,),
        ).fetchone()
        if not row:
            return "unavailable"
        status = row["status"]
        if status in ("ok", "watch", "alert", "unavailable"):
            return status  # type: ignore[return-value]
        return "unavailable"

    def set_trend_state(
        self,
        metric: str,
        status: TrendStatus,
        *,
        latest: Optional[float],
        baseline: Optional[float],
        message: str,
    ) -> None:
        conn = self.db.connect()
        now = _iso()
        conn.execute(
            """
            INSERT INTO trend_state (metric, status, latest, baseline, message, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric) DO UPDATE SET
                status=excluded.status,
                latest=excluded.latest,
                baseline=excluded.baseline,
                message=excluded.message,
                updated_at=excluded.updated_at
            """,
            (metric, status, latest, baseline, message, now),
        )
        conn.commit()

    def list_maintenance(self) -> list[dict[str, Any]]:
        conn = self.db.connect()
        rows = conn.execute(
            """
            SELECT * FROM maintenance_reminders
            ORDER BY
              CASE status
                WHEN 'overdue' THEN 0
                WHEN 'due_soon' THEN 1
                WHEN 'upcoming' THEN 2
                ELSE 3
              END,
              title ASC
            """
        ).fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "kind": row["kind"],
                "due_label": row["due_label"],
                "interval_mi": row["interval_mi"],
                "interval_months": row["interval_months"],
                "last_service_label": row["last_service_label"],
                "status": row["status"],
                "note": row["note"],
                "simulated": bool(row["simulated"]),
                "source": row["source"],
            }
            for row in rows
        ]

    def record_alert_event(
        self,
        alert_id: str,
        *,
        severity: str,
        title: str,
        detail: str,
        metric: Optional[str],
        active: bool,
        simulated: bool,
    ) -> None:
        """Deduplicate repetitive alerts by alert_id — update if active state unchanged recently."""
        conn = self.db.connect()
        now = _iso()
        existing = conn.execute(
            "SELECT id FROM health_alerts WHERE alert_key=? AND active=1",
            (alert_id,),
        ).fetchone()
        if active and existing:
            conn.execute(
                """
                UPDATE health_alerts
                SET detail=?, severity=?, title=?, updated_at=?
                WHERE id=?
                """,
                (detail, severity, title, now, existing["id"]),
            )
        elif active:
            conn.execute(
                """
                INSERT INTO health_alerts (
                    id, alert_key, severity, title, detail, metric,
                    active, simulated, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    alert_id,
                    severity,
                    title,
                    detail,
                    metric,
                    1 if simulated else 0,
                    now,
                    now,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE health_alerts
                SET active=0, updated_at=?
                WHERE alert_key=? AND active=1
                """,
                (now, alert_id),
            )
        conn.commit()

    def list_active_alerts(self) -> list[dict[str, Any]]:
        conn = self.db.connect()
        rows = conn.execute(
            """
            SELECT * FROM health_alerts
            WHERE active=1
            ORDER BY
              CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
              updated_at DESC
            """
        ).fetchall()
        return [
            {
                "id": row["alert_key"],
                "severity": row["severity"],
                "title": row["title"],
                "detail": row["detail"],
                "metric": row["metric"],
                "active": True,
                "simulated": bool(row["simulated"]),
            }
            for row in rows
        ]
