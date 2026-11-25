"""Short-lived voice session context for natural follow-ups (~15s)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


DEFAULT_FOLLOWUP_TIMEOUT_S = 15.0


@dataclass
class SessionSnapshot:
    last_intent: Optional[str] = None
    last_reply: Optional[str] = None
    expires_at: float = 0.0
    active: bool = False

    def to_api(self, *, now: Optional[float] = None) -> dict[str, Any]:
        mono = time.monotonic() if now is None else now
        remaining = max(0.0, self.expires_at - mono) if self.active else 0.0
        return {
            "active": self.active and remaining > 0,
            "last_intent": self.last_intent if self.active and remaining > 0 else None,
            "followup_remaining_s": round(remaining, 2),
            "timeout_s": DEFAULT_FOLLOWUP_TIMEOUT_S,
        }


@dataclass
class SessionContext:
    """In-memory follow-up window after a successful voice reply."""

    timeout_s: float = DEFAULT_FOLLOWUP_TIMEOUT_S
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _last_intent: Optional[str] = None
    _last_reply: Optional[str] = None
    _expires_at: float = 0.0

    def prior_intent(self) -> Optional[str]:
        with self._lock:
            self._expire_if_needed()
            return self._last_intent

    def remember(self, intent: str, reply: str) -> SessionSnapshot:
        with self._lock:
            if intent == "end_session":
                self._clear_unlocked()
                return self._snapshot_unlocked()
            now = time.monotonic()
            self._last_intent = intent
            self._last_reply = reply
            self._expires_at = now + self.timeout_s
            return self._snapshot_unlocked(now=now)

    def end(self) -> SessionSnapshot:
        with self._lock:
            self._clear_unlocked()
            return self._snapshot_unlocked()

    def snapshot(self) -> SessionSnapshot:
        with self._lock:
            return self._snapshot_unlocked()

    def _expire_if_needed(self) -> None:
        if self._last_intent is None:
            return
        if time.monotonic() >= self._expires_at:
            self._clear_unlocked()

    def _clear_unlocked(self) -> None:
        self._last_intent = None
        self._last_reply = None
        self._expires_at = 0.0

    def _snapshot_unlocked(self, *, now: Optional[float] = None) -> SessionSnapshot:
        mono = time.monotonic() if now is None else now
        active = bool(self._last_intent and mono < self._expires_at)
        if not active and self._last_intent is not None and mono >= self._expires_at:
            # Lazy clear so API stays honest.
            self._clear_unlocked()
            active = False
        return SessionSnapshot(
            last_intent=self._last_intent if active else None,
            last_reply=self._last_reply if active else None,
            expires_at=self._expires_at if active else 0.0,
            active=active,
        )
