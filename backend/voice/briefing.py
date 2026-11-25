"""Startup briefing: fuel + health only. No previous-trip fuel cost."""

from __future__ import annotations

from typing import Any, Optional


def build_startup_briefing(
    *,
    fuel_level_pct: Optional[float],
    fuel_quality: Optional[str],
    health: Optional[dict[str, Any]],
    maintenance: Optional[dict[str, Any]] = None,
    simulated: bool = True,
) -> dict[str, Any]:
    """Concise drive-start lines. Honest when data is missing.

    Never includes previous-trip fuel cost. Never claims the car is healthy
    solely because no DTCs are present.
    """
    parts: list[str] = []
    unavailable: list[str] = []

    if fuel_level_pct is None or fuel_quality == "unavailable":
        parts.append("Fuel level is unavailable.")
        unavailable.append("fuel_level")
    else:
        pct = round(float(fuel_level_pct))
        parts.append(f"Fuel is about {pct} percent.")

    active_codes: list[str] = []
    if health is None:
        parts.append("Vehicle health data is unavailable.")
        unavailable.append("health")
    else:
        dtcs = health.get("dtcs") or []
        active_codes = [
            str(d.get("code"))
            for d in dtcs
            if isinstance(d, dict) and d.get("status") == "active" and d.get("code")
        ]
        if active_codes:
            listed = ", ".join(active_codes[:4])
            more = "" if len(active_codes) <= 4 else f" and {len(active_codes) - 4} more"
            parts.append(
                f"Active diagnostic codes: {listed}{more}. "
                "Codes are not confirmed diagnoses. Factory warnings stay authoritative."
            )
        else:
            parts.append(
                "No active diagnostic codes reported — "
                "that is not a clean bill of health."
            )

        alerts = [
            a
            for a in (health.get("alerts") or [])
            if isinstance(a, dict) and a.get("active") and a.get("severity") in ("warning", "critical")
        ]
        trend_alerts = [
            a
            for a in alerts
            if str(a.get("id", "")).startswith("trend:")
        ]
        if trend_alerts:
            titles = "; ".join(
                str(a.get("title") or a.get("detail") or "telemetry watch")
                for a in trend_alerts[:2]
            )
            parts.append(f"Telemetry watch: {titles}.")

    reminder_line = _pick_maintenance_line(maintenance)
    if reminder_line:
        parts.append(reminder_line)

    spoken = " ".join(parts)
    return {
        "ok": True,
        "kind": "startup_briefing",
        "spoken": spoken,
        "lines": parts,
        "fuel_level_pct": None if fuel_level_pct is None else round(float(fuel_level_pct), 1),
        "active_dtc_codes": active_codes,
        "unavailable": unavailable,
        "includes_previous_trip_fuel_cost": False,
        "simulated": simulated,
        "note": (
            "Startup briefing uses available fuel + health only. "
            "Previous-trip fuel cost is intentionally omitted. "
            "Audio playback / background TTS on iPhone PWA is unproven "
            "(audio feasibility gate still open)."
        ),
    }


def _pick_maintenance_line(maintenance: Optional[dict[str, Any]]) -> Optional[str]:
    if not maintenance:
        return None
    reminders = maintenance.get("reminders") or []
    priority = ("overdue", "due_soon", "upcoming", "unknown")
    ranked: list[dict[str, Any]] = []
    for status in priority:
        for r in reminders:
            if isinstance(r, dict) and r.get("status") == status:
                ranked.append(r)
        if ranked:
            break
    if not ranked:
        return None
    top = ranked[0]
    title = str(top.get("title") or "Maintenance")
    due = str(top.get("due_label") or "").strip()
    status = str(top.get("status") or "unknown").replace("_", " ")
    if due:
        return f"Maintenance note ({status}): {title} — {due}."
    return f"Maintenance note ({status}): {title}."
