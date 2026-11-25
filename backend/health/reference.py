"""Vetted static OBD-II code reference (read-only explanations).

Sources: SAE J2012 / EPA common OBD-II definitions (generic powertrain codes).
A code is a stored fault flag — not a confirmed diagnosis or repair order.
"""

from __future__ import annotations

from typing import Any, Optional

# Curated subset used by the simulator and explanations. Keep wording cautious.
DTC_REFERENCE: dict[str, dict[str, Any]] = {
    "P0420": {
        "title": "Catalyst system efficiency below threshold (Bank 1)",
        "summary": (
            "The powertrain control module reported that the catalytic converter "
            "on bank 1 may not be operating as efficiently as expected."
        ),
        "common_causes": [
            "Aging or damaged catalytic converter",
            "Exhaust leak upstream of the converter",
            "Faulty or slow oxygen / air-fuel ratio sensor",
            "Engine misfire or rich/lean condition affecting catalyst efficiency",
        ],
        "interpretation_note": (
            "This is a diagnostic trouble code, not a confirmed diagnosis. "
            "A technician should verify with live data and inspections. "
            "Factory warnings remain authoritative."
        ),
        "severity": "warning",
        "system": "emissions",
    },
    "P0300": {
        "title": "Random / multiple cylinder misfire detected",
        "summary": (
            "The control module detected misfires that are not limited to a "
            "single cylinder."
        ),
        "common_causes": [
            "Ignition system wear (plugs, coils, wires)",
            "Fuel delivery issues",
            "Vacuum leaks or intake problems",
            "Mechanical issues (compression, timing)",
        ],
        "interpretation_note": (
            "This is a diagnostic trouble code, not a confirmed diagnosis. "
            "Continued driving with active misfires can damage the catalyst. "
            "Factory warnings remain authoritative."
        ),
        "severity": "critical",
        "system": "ignition",
    },
    "P0171": {
        "title": "System too lean (Bank 1)",
        "summary": (
            "The fuel trim system reported a lean condition on bank 1 — more air "
            "relative to fuel than the target mixture."
        ),
        "common_causes": [
            "Vacuum or intake air leak",
            "Dirty or failing mass airflow sensor",
            "Weak fuel pump or clogged filter",
            "Faulty oxygen sensor readings",
        ],
        "interpretation_note": (
            "This is a diagnostic trouble code, not a confirmed diagnosis. "
            "Factory warnings remain authoritative."
        ),
        "severity": "warning",
        "system": "fuel",
    },
    "P0128": {
        "title": "Coolant thermostat (coolant temperature below thermostat regulating temperature)",
        "summary": (
            "Engine coolant is not reaching the expected temperature in the "
            "expected time — often related to thermostat or cooling system behavior."
        ),
        "common_causes": [
            "Stuck-open thermostat",
            "Coolant level or mixture issues",
            "Faulty coolant temperature sensor",
            "Extended idle / very cold ambient conditions",
        ],
        "interpretation_note": (
            "This is a diagnostic trouble code, not a confirmed diagnosis. "
            "Factory warnings remain authoritative."
        ),
        "severity": "info",
        "system": "cooling",
    },
    "P0562": {
        "title": "System voltage low",
        "summary": (
            "The control module observed system voltage below the expected range "
            "while monitoring electrical system health."
        ),
        "common_causes": [
            "Weak or failing battery",
            "Charging system / alternator issues",
            "Poor ground or cable connections",
            "High electrical load with engine off",
        ],
        "interpretation_note": (
            "This is a diagnostic trouble code, not a confirmed diagnosis. "
            "Factory warnings remain authoritative."
        ),
        "severity": "warning",
        "system": "electrical",
    },
}


def lookup_code(code: str) -> Optional[dict[str, Any]]:
    key = (code or "").strip().upper()
    return DTC_REFERENCE.get(key)


def explain_code(code: str) -> dict[str, Any]:
    """Return an explanation payload that never claims a confirmed diagnosis."""
    key = (code or "").strip().upper()
    ref = lookup_code(key)
    if ref is None:
        return {
            "code": key,
            "title": "Unknown or unsupported code",
            "summary": (
                "No vetted reference entry is available for this code in AccordOS yet."
            ),
            "common_causes": [],
            "interpretation": "code",
            "interpretation_note": (
                "This is a diagnostic trouble code, not a confirmed diagnosis. "
                "Consult factory documentation or a qualified technician. "
                "Factory warnings remain authoritative."
            ),
            "severity": "info",
            "system": "unknown",
            "reference_found": False,
        }
    return {
        "code": key,
        "title": ref["title"],
        "summary": ref["summary"],
        "common_causes": list(ref["common_causes"]),
        "interpretation": "code",
        "interpretation_note": ref["interpretation_note"],
        "severity": ref["severity"],
        "system": ref["system"],
        "reference_found": True,
    }
