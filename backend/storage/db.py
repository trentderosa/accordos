"""SQLite persistence with versioned schema migrations."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Union

from .migrations import TARGET_VERSION, apply_migrations


class Database:
    def __init__(self, path: Optional[Union[Path, str]] = None) -> None:
        """Open a SQLite database.

        - ``None`` → private in-memory DB (unique per instance; good for tests)
        - ``":memory:"`` → same as None
        - path string/Path → on-disk file (parents created on connect)
        """
        if path is None or str(path) == ":memory:":
            # Unique shared-cache URI so one connection sees its own schema.
            self.path: Union[Path, str] = (
                f"file:accordos_{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
            self._uri = True
        else:
            self.path = Path(path)
            self._uri = False
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            if self._uri:
                self._conn = sqlite3.connect(
                    str(self.path), uri=True, check_same_thread=False
                )
            else:
                path = Path(self.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta "
                "(key TEXT PRIMARY KEY, value TEXT)"
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('version', '0')"
            )
            self._conn.commit()
            apply_migrations(self._conn, self._raw_version())
        return self._conn

    def migrate(self) -> int:
        self.connect()
        return self.schema_version()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _raw_version(self) -> int:
        assert self._conn is not None
        row = self._conn.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def schema_version(self) -> int:
        self.connect()
        return self._raw_version()

    @property
    def target_version(self) -> int:
        return TARGET_VERSION
