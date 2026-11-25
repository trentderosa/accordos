"""Deterministic local text → intent routing. No LLM, no shell."""

from __future__ import annotations

import re
from typing import Optional

# Canonical supported intents (allowlist only).
SUPPORTED = frozenset(
    {
        "fuel_level",
        "range_estimate",
        "last_trip",
        "check_engine",
        "navigate_home",
        "pause_spotify",
        "end_session",
    }
)

# Follow-up phrases that need recent session context (~15s).
FOLLOWUP_RANGE = re.compile(
    r"\b("
    r"how\s+far|"
    r"that\s+get\s+me|"
    r"range|"
    r"how\s+much\s+(farther|further)|"
    r"will\s+that\s+last"
    r")\b",
    re.I,
)

# Ordered pattern table: first match wins.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "end_session",
        re.compile(
            r"\b("
            r"that'?s\s+all|"
            r"thats\s+all|"
            r"never\s+mind|"
            r"nevermind|"
            r"stop\s+listening|"
            r"cancel|"
            r"goodbye|"
            r"good\s+bye|"
            r"end\s+session|"
            r"i'?m\s+done"
            r")\b",
            re.I,
        ),
    ),
    (
        "pause_spotify",
        re.compile(
            r"\b("
            r"pause\s+(spotify|music|the\s+music|playback)|"
            r"spotify\s+pause|"
            r"stop\s+(the\s+)?(music|spotify)|"
            r"mute\s+(spotify|music)"
            r")\b",
            re.I,
        ),
    ),
    (
        "navigate_home",
        re.compile(
            r"\b("
            r"navigate\s+home|"
            r"take\s+me\s+home|"
            r"go\s+home|"
            r"directions?\s+(to\s+)?home|"
            r"drive\s+(me\s+)?home|"
            r"route\s+home"
            r")\b",
            re.I,
        ),
    ),
    (
        "check_engine",
        re.compile(
            r"\b("
            r"check[\s-]?engine|"
            r"cel\b|"
            r"trouble\s+code|"
            r"diagnostic\s+code|"
            r"dtc|"
            r"engine\s+light|"
            r"why\s+is\s+(my\s+)?(check[\s-]?engine|engine\s+light)"
            r")\b",
            re.I,
        ),
    ),
    (
        "last_trip",
        re.compile(
            r"\b("
            r"last\s+trip|"
            r"previous\s+trip|"
            r"how\s+was\s+(my\s+)?(last\s+)?trip|"
            r"trip\s+(summary|report|history)|"
            r"how\s+did\s+(my\s+)?(last\s+)?(drive|trip)\s+go"
            r")\b",
            re.I,
        ),
    ),
    (
        "range_estimate",
        re.compile(
            r"\b("
            r"how\s+far\s+will\s+that\s+get\s+me|"
            r"how\s+far\s+can\s+i\s+go|"
            r"(estimated?\s+)?range|"
            r"how\s+much\s+range|"
            r"miles?\s+(left|remaining)|"
            r"distance\s+(left|remaining)|"
            r"how\s+far\s+(on\s+)?(this\s+)?(tank|fuel|gas)"
            r")\b",
            re.I,
        ),
    ),
    (
        "fuel_level",
        re.compile(
            r"\b("
            r"how\s+much\s+(fuel|gas)|"
            r"fuel\s+(level|left|remaining)|"
            r"gas\s+(level|left|remaining)|"
            r"tank\s+(level|left|remaining)|"
            r"(fuel|gas)\s+in\s+the\s+tank|"
            r"what'?s\s+(my\s+)?(fuel|gas)|"
            r"fuel\b|"
            r"\bgas\b"
            r")\b",
            re.I,
        ),
    ),
)


def normalize_intent(intent: Optional[str]) -> Optional[str]:
    if intent is None:
        return None
    key = intent.strip().lower().replace("-", "_").replace(" ", "_")
    if key in ("", "auto", "detect", "from_text"):
        return None
    return key


def route_text(
    text: str,
    *,
    prior_intent: Optional[str] = None,
) -> tuple[Optional[str], str]:
    """Map free text to a supported intent.

    Returns ``(intent_or_None, reason)``.
    Unknown → ``(None, "unknown")``.
    Follow-ups use ``prior_intent`` when the phrase is ambiguous.
    """
    raw = (text or "").strip()
    if not raw:
        return None, "empty"

    # Explicit follow-up after fuel → range (handoff example).
    if prior_intent == "fuel_level" and FOLLOWUP_RANGE.search(raw):
        # Prefer range when prior was fuel, even for short "how far?"
        if re.search(r"\b(how\s+far|range|that\s+get|farther|further|last)\b", raw, re.I):
            return "range_estimate", "followup_after_fuel"

    for intent, pattern in _PATTERNS:
        if pattern.search(raw):
            return intent, "pattern"

    # Short follow-ups that only make sense with context.
    if prior_intent == "fuel_level" and re.search(
        r"^(and\s+)?(the\s+)?(range|distance)\??$", raw, re.I
    ):
        return "range_estimate", "followup_after_fuel"

    if prior_intent == "check_engine" and re.search(
        r"\b(what\s+does\s+(that|it)\s+mean|explain|more)\b", raw, re.I
    ):
        return "check_engine", "followup_check_engine"

    return None, "unknown"


def resolve_command(
    *,
    intent: Optional[str] = None,
    text: Optional[str] = None,
    prior_intent: Optional[str] = None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Resolve intent from explicit allowlist and/or text.

    Returns ``(intent_or_None, resolve_note, normalized_text)``.
    """
    normalized_text = (text or "").strip() or None
    explicit = normalize_intent(intent)

    if explicit is not None:
        if explicit not in SUPPORTED:
            return None, "unsupported_intent", normalized_text
        return explicit, "explicit", normalized_text

    if normalized_text:
        routed, note = route_text(normalized_text, prior_intent=prior_intent)
        return routed, note, normalized_text

    return None, "missing_intent_and_text", None
