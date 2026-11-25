"""SQLite schema migrations for AccordOS persistence."""

from __future__ import annotations

import sqlite3
from typing import Callable

MigrationFn = Callable[[sqlite3.Connection], None]

# Current schema version after applying all migrations below.
TARGET_VERSION = 3


def _migrate_to_1(conn: sqlite3.Connection) -> None:
    """Trips, samples, and checkpoints for Phase 3 trip intelligence."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            duration_s REAL,
            distance_mi REAL,
            avg_speed_mph REAL,
            max_speed_mph REAL,
            idle_time_s REAL,
            fuel_start_pct REAL,
            fuel_end_pct REAL,
            fuel_used_pct REAL,
            fuel_estimate_status TEXT NOT NULL DEFAULT 'unavailable',
            efficiency_score REAL,
            efficiency_confidence REAL,
            efficiency_status TEXT NOT NULL DEFAULT 'withheld',
            efficiency_detail TEXT,
            incomplete INTEGER NOT NULL DEFAULT 0,
            simulated INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'simulator',
            title TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trip_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            ts TEXT NOT NULL,
            speed_mph REAL,
            rpm REAL,
            fuel_level_pct REAL,
            coolant_c REAL,
            engine_load_pct REAL,
            voltage_v REAL,
            quality TEXT,
            mode TEXT,
            communicating INTEGER NOT NULL DEFAULT 1,
            UNIQUE(trip_id, ts)
        );

        CREATE INDEX IF NOT EXISTS idx_trip_samples_trip_ts
            ON trip_samples(trip_id, ts);

        CREATE TABLE IF NOT EXISTS trip_checkpoints (
            trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
            seq INTEGER NOT NULL,
            ts TEXT NOT NULL,
            state TEXT NOT NULL,
            distance_mi REAL,
            max_speed_mph REAL,
            idle_time_s REAL,
            sample_count INTEGER,
            PRIMARY KEY (trip_id, seq)
        );
        """
    )


def _migrate_to_2(conn: sqlite3.Connection) -> None:
    """Monotonic sync revisions for Pi-authoritative incremental sync."""
    cols = {
        row[1] for row in conn.execute("PRAGMA table_info(trips)").fetchall()
    }
    if "revision" not in cols:
        conn.execute("ALTER TABLE trips ADD COLUMN revision INTEGER")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sync_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trips_revision
            ON trips(revision);
        """
    )

    rows = conn.execute(
        """
        SELECT id FROM trips
        WHERE state IN ('finalized', 'recovered')
        ORDER BY COALESCE(updated_at, start_ts) ASC, id ASC
        """
    ).fetchall()
    next_rev = 1
    for row in rows:
        conn.execute(
            "UPDATE trips SET revision=? WHERE id=?",
            (next_rev, row[0]),
        )
        next_rev += 1

    conn.execute(
        """
        INSERT INTO sync_meta(key, value) VALUES ('next_revision', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(next_rev),),
    )
    conn.commit()


def _migrate_to_3(conn: sqlite3.Connection) -> None:
    """Health core: diagnostic history, telemetry trends, maintenance reminders."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_events (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            status TEXT NOT NULL,
            title TEXT,
            summary TEXT,
            explanation_json TEXT,
            severity TEXT,
            system TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'simulator',
            simulated INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_diagnostic_events_code_status
            ON diagnostic_events(code, status);

        CREATE TABLE IF NOT EXISTS telemetry_trend_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            ts TEXT NOT NULL,
            value REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trend_samples_metric_ts
            ON telemetry_trend_samples(metric, ts);

        CREATE TABLE IF NOT EXISTS trend_state (
            metric TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            latest REAL,
            baseline REAL,
            message TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS maintenance_reminders (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,
            due_label TEXT NOT NULL,
            interval_mi REAL,
            interval_months INTEGER,
            last_service_label TEXT,
            status TEXT NOT NULL DEFAULT 'unknown',
            note TEXT,
            simulated INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'user_interval',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS health_alerts (
            id TEXT PRIMARY KEY,
            alert_key TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL,
            metric TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            simulated INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_health_alerts_key_active
            ON health_alerts(alert_key, active);
        """
    )


MIGRATIONS: dict[int, MigrationFn] = {
    1: _migrate_to_1,
    2: _migrate_to_2,
    3: _migrate_to_3,
}


def apply_migrations(conn: sqlite3.Connection, current: int) -> int:
    """Apply pending migrations in order. Returns the new schema version."""
    version = current
    for target in sorted(MIGRATIONS):
        if target <= version:
            continue
        MIGRATIONS[target](conn)
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES ('version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(target),),
        )
        conn.commit()
        version = target
    return version
