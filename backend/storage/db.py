"""Minimal SQLite facade — schema migrations arrive with trip persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(":memory:")
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = str(self.path)
            self._conn = sqlite3.connect(uri, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '0')"
            )
            self._conn.commit()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def schema_version(self) -> int:
        row = self.connect().execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        return int(row["value"]) if row else 0
