"""Read-only health / maintenance stubs — never clears codes or issues commands."""

from __future__ import annotations

from typing import Any


class HealthService:
    def status(self) -> dict[str, Any]:
        return {
            "dtcs": [],
            "alerts": [],
            "note": "Phase 1 stub — no real diagnostics. Factory warnings remain authoritative.",
            "read_only": True,
            "simulated": True,
        }

    def maintenance(self) -> dict[str, Any]:
        return {
            "reminders": [],
            "note": "Phase 1 stub — maintenance reminders arrive later",
            "simulated": True,
        }
