"""Deterministic voice intent service — supported intents only, no shell."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from backend.infotainment.links import maps_deep_links, spotify_stub_action

from .briefing import build_startup_briefing
from .context import SessionContext
from .intents import SUPPORTED, resolve_command


class _HasLatest(Protocol):
    @property
    def latest(self) -> Any: ...


class _TripReader(Protocol):
    def list_trips(self) -> list[dict[str, Any]]: ...


class _HealthReader(Protocol):
    def status(self) -> dict[str, Any]: ...

    def maintenance(self) -> dict[str, Any]: ...


# Encoded deep-link stubs — no fabricated map/police data; iOS launch unproven.
HOME_DEEP_LINKS = maps_deep_links("Home")


class VoiceService:
    """Route text/intent → reply using live telemetry, trips, and health.

    Safety:
    - Allowlisted intents only
    - Never executes shell or arbitrary commands
    - No paid LLM
    - No audio retention (text in → reply out; no recording store)
    """

    def __init__(
        self,
        *,
        telemetry: Optional[_HasLatest] = None,
        trips: Optional[_TripReader] = None,
        health: Optional[_HealthReader] = None,
        followup_timeout_s: float = 15.0,
    ) -> None:
        self.telemetry = telemetry
        self.trips = trips
        self.health = health
        self.session = SessionContext(timeout_s=followup_timeout_s)

    def bind(
        self,
        *,
        telemetry: Optional[_HasLatest] = None,
        trips: Optional[_TripReader] = None,
        health: Optional[_HealthReader] = None,
    ) -> None:
        if telemetry is not None:
            self.telemetry = telemetry
        if trips is not None:
            self.trips = trips
        if health is not None:
            self.health = health

    def handle(
        self,
        intent: Optional[str] = None,
        text: Optional[str] = None,
    ) -> dict[str, Any]:
        prior = self.session.prior_intent()
        resolved, note, normalized_text = resolve_command(
            intent=intent,
            text=text,
            prior_intent=prior,
        )

        if resolved is None:
            snap = self.session.snapshot()
            return {
                "ok": False,
                "intent": None,
                "resolve": note,
                "reply": (
                    "I don't support that yet. Try fuel, range, last trip, "
                    "check engine, navigate home, pause Spotify, or that's all."
                ),
                "text": normalized_text,
                "prior_intent": prior,
                "session": snap.to_api(),
                "shell_executed": False,
                "note": "Allowlisted intents only — no shell execution",
            }

        reply_payload = self._dispatch(resolved)
        session_snap = self.session.remember(resolved, reply_payload["reply"])
        if resolved == "end_session":
            session_snap = self.session.end()

        return {
            "ok": True,
            "intent": resolved,
            "resolve": note,
            "reply": reply_payload["reply"],
            "text": normalized_text,
            "prior_intent": prior,
            "session": session_snap.to_api(),
            "shell_executed": False,
            "action": reply_payload.get("action"),
            "data": reply_payload.get("data"),
            "unavailable": reply_payload.get("unavailable", []),
            "simulated": reply_payload.get("simulated", True),
            "note": reply_payload.get(
                "note",
                "Deterministic local intent — no LLM, no shell",
            ),
        }

    def briefing(self) -> dict[str, Any]:
        sample = self._latest_sample()
        fuel = None
        quality = None
        simulated = True
        if sample is not None:
            fuel = getattr(sample, "fuel_level_pct", None)
            if isinstance(sample, dict):
                fuel = sample.get("fuel_level_pct")
                quality = sample.get("quality")
                simulated = bool(sample.get("simulated", True))
            else:
                quality = getattr(sample, "quality", None)
                simulated = bool(getattr(sample, "simulated", True))

        health_payload = None
        maintenance_payload = None
        if self.health is not None:
            try:
                health_payload = self.health.status()
            except Exception:  # noqa: BLE001 — briefing must stay honest
                health_payload = None
            try:
                maintenance_payload = self.health.maintenance()
            except Exception:  # noqa: BLE001
                maintenance_payload = None

        return build_startup_briefing(
            fuel_level_pct=fuel if isinstance(fuel, (int, float)) else None,
            fuel_quality=quality if isinstance(quality, str) else None,
            health=health_payload,
            maintenance=maintenance_payload,
            simulated=simulated,
        )

    def supported(self) -> list[str]:
        return sorted(SUPPORTED)

    def _dispatch(self, intent: str) -> dict[str, Any]:
        handlers = {
            "fuel_level": self._fuel_level,
            "range_estimate": self._range_estimate,
            "last_trip": self._last_trip,
            "check_engine": self._check_engine,
            "navigate_home": self._navigate_home,
            "pause_spotify": self._pause_spotify,
            "end_session": self._end_session,
        }
        return handlers[intent]()

    def _latest_sample(self) -> Any:
        if self.telemetry is None:
            return None
        return getattr(self.telemetry, "latest", None)

    def _sample_fields(self) -> dict[str, Any]:
        sample = self._latest_sample()
        if sample is None:
            return {"quality": "unavailable", "simulated": True}
        if isinstance(sample, dict):
            return sample
        if hasattr(sample, "model_dump"):
            return sample.model_dump(mode="json")
        return {
            "fuel_level_pct": getattr(sample, "fuel_level_pct", None),
            "quality": getattr(sample, "quality", None),
            "simulated": getattr(sample, "simulated", True),
            "message": getattr(sample, "message", None),
        }

    def _fuel_level(self) -> dict[str, Any]:
        fields = self._sample_fields()
        fuel = fields.get("fuel_level_pct")
        quality = fields.get("quality")
        simulated = bool(fields.get("simulated", True))
        if fuel is None or quality == "unavailable":
            return {
                "reply": "Fuel level is unavailable right now.",
                "unavailable": ["fuel_level"],
                "simulated": simulated,
                "data": {"fuel_level_pct": None},
            }
        pct = round(float(fuel))
        return {
            "reply": f"Fuel is about {pct} percent.",
            "unavailable": [],
            "simulated": simulated,
            "data": {"fuel_level_pct": round(float(fuel), 1)},
        }

    def _range_estimate(self) -> dict[str, Any]:
        # Range needs calibrated fuel economy inputs — not inventing miles.
        fields = self._sample_fields()
        fuel = fields.get("fuel_level_pct")
        simulated = bool(fields.get("simulated", True))
        note = (
            "Estimated range is unavailable until fuel economy is calibrated "
            "from supported inputs. Fuel percent alone is not enough."
        )
        fuel_bit = ""
        if fuel is not None and fields.get("quality") != "unavailable":
            fuel_bit = f" Fuel is about {round(float(fuel))} percent,"
            fuel_bit += " but range still isn't estimated."
        return {
            "reply": (
                f"I don't have a reliable range estimate yet.{fuel_bit} {note}"
            ).strip(),
            "unavailable": ["range_estimate"],
            "simulated": simulated,
            "data": {
                "range_mi": None,
                "fuel_level_pct": None
                if fuel is None
                else round(float(fuel), 1),
            },
            "note": note,
        }

    def _last_trip(self) -> dict[str, Any]:
        if self.trips is None:
            return {
                "reply": "Trip history is unavailable.",
                "unavailable": ["last_trip"],
                "simulated": True,
                "data": {"trip": None},
            }
        try:
            trips = list(self.trips.list_trips())
        except Exception:  # noqa: BLE001
            return {
                "reply": "Trip history is unavailable.",
                "unavailable": ["last_trip"],
                "simulated": True,
                "data": {"trip": None},
            }

        # Prefer finalized/recovered; fall back to first closed trip with an end.
        pick = None
        open_trip = None
        for t in trips:
            if not isinstance(t, dict):
                continue
            state = str(t.get("state") or t.get("status") or "")
            if state in ("starting", "active", "ending"):
                if open_trip is None:
                    open_trip = t
                continue
            if state in ("finalized", "recovered", "complete", "completed"):
                pick = t
                break
            if t.get("end") and pick is None:
                pick = t

        if pick is None and open_trip is not None:
            dist = open_trip.get("distance_mi")
            dist_s = (
                f"{float(dist):.1f} miles so far"
                if dist is not None
                else "in progress"
            )
            return {
                "reply": (
                    f"Your current trip is still open — {dist_s}. "
                    "I'll summarize it when it finalizes."
                ),
                "unavailable": [],
                "simulated": bool(open_trip.get("simulated", True)),
                "data": {"trip": open_trip, "open": True},
            }

        if pick is None:
            return {
                "reply": "I don't have a completed trip to summarize yet.",
                "unavailable": ["last_trip"],
                "simulated": True,
                "data": {"trip": None},
            }

        title = pick.get("title") or "Your last trip"
        dist = pick.get("distance_mi")
        dur = pick.get("duration_min")
        eff = pick.get("efficiency_score")
        eff_status = pick.get("efficiency_status")
        bits = [str(title)]
        if dist is not None:
            bits.append(f"{float(dist):.1f} miles")
        if dur is not None:
            bits.append(f"{round(float(dur))} minutes")
        if pick.get("incomplete"):
            bits.append("marked incomplete")
        if eff_status == "available" and eff is not None:
            bits.append(f"efficiency {round(float(eff))}")
        elif eff_status == "withheld":
            bits.append("efficiency withheld")
        reply = ". ".join(bits) + "."
        return {
            "reply": reply,
            "unavailable": [],
            "simulated": bool(pick.get("simulated", True)),
            "data": {"trip": pick},
        }

    def _check_engine(self) -> dict[str, Any]:
        if self.health is None:
            return {
                "reply": (
                    "Diagnostic data is unavailable. "
                    "Factory warnings remain authoritative."
                ),
                "unavailable": ["check_engine"],
                "simulated": True,
                "data": {"dtcs": []},
            }
        try:
            status = self.health.status()
        except Exception:  # noqa: BLE001
            return {
                "reply": (
                    "Diagnostic data is unavailable. "
                    "Factory warnings remain authoritative."
                ),
                "unavailable": ["check_engine"],
                "simulated": True,
                "data": {"dtcs": []},
            }

        dtcs = [d for d in (status.get("dtcs") or []) if isinstance(d, dict)]
        active = [d for d in dtcs if d.get("status") == "active"]
        simulated = bool(status.get("simulated", True))
        if not active:
            return {
                "reply": (
                    "No active diagnostic codes are reported. "
                    "Absence of codes is not a clean bill of health. "
                    "Factory warnings remain authoritative."
                ),
                "unavailable": [],
                "simulated": simulated,
                "data": {"dtcs": [], "active_dtc_count": 0},
            }

        lines: list[str] = []
        for d in active[:3]:
            code = d.get("code") or "?"
            title = d.get("title") or "Diagnostic code"
            summary = d.get("summary") or ""
            lines.append(f"{code}: {title}. {summary}".strip())
        extra = ""
        if len(active) > 3:
            extra = f" Plus {len(active) - 3} more active codes."
        disclaimer = (
            " These are codes, not confirmed diagnoses. "
            "Factory warnings remain authoritative. AccordOS never clears codes."
        )
        return {
            "reply": " ".join(lines) + extra + disclaimer,
            "unavailable": [],
            "simulated": simulated,
            "data": {
                "dtcs": active,
                "active_dtc_count": len(active),
            },
        }

    def _navigate_home(self) -> dict[str, Any]:
        return {
            "reply": (
                "Navigation home is a deep-link stub for now. "
                "Open Waze or Apple Maps when you're parked and ready — "
                "iOS may require a user gesture to launch from the PWA."
            ),
            "unavailable": [],
            "simulated": True,
            "action": {
                "type": "deep_link_stub",
                "destination": "home",
                "links": HOME_DEEP_LINKS,
                "launched": False,
            },
            "data": {"links": HOME_DEEP_LINKS},
            "note": "Deep link stub only — does not force-launch maps apps",
        }

    def _pause_spotify(self) -> dict[str, Any]:
        action = spotify_stub_action(requested="pause")
        return {
            "reply": (
                "I can't control Spotify from AccordOS yet. "
                "Open Spotify or ask Siri for now — no client secrets in the app."
            ),
            "unavailable": ["spotify_api"],
            "simulated": True,
            "action": action,
            "note": (
                "Spotify open/Siri stub only; OAuth PKCE documented in "
                "docs/infotainment.md — not wired; core app works without Spotify"
            ),
        }

    def _end_session(self) -> dict[str, Any]:
        return {
            "reply": "Okay.",
            "unavailable": [],
            "simulated": True,
            "action": {"type": "end_session"},
        }
