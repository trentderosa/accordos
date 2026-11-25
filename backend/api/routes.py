"""REST + WebSocket routes matching handoff §12."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, model_validator

from backend.voice import require_voice_access
from simulator.provider import SimulatorProvider

router = APIRouter()


class VoiceCommand(BaseModel):
    intent: Optional[str] = Field(default=None, max_length=64)
    text: Optional[str] = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def require_intent_or_text(self) -> "VoiceCommand":
        intent = (self.intent or "").strip()
        text = (self.text or "").strip()
        if not intent and not text:
            raise ValueError("Provide intent and/or text")
        return self


class ScenarioBody(BaseModel):
    scenario: str = Field(..., min_length=1, max_length=32)


@router.get("/api/capabilities")
async def capabilities(request: Request):
    svc = request.app.state.telemetry
    return svc.provider.capabilities()


@router.get("/api/status")
async def status(request: Request):
    svc = request.app.state.telemetry
    trips = request.app.state.trips
    voice = request.app.state.voice
    return {
        "app": "AccordOS",
        "phase": 4,
        "api_version": "0.4.1",
        "connection": svc.connection_status,
        "trip": {
            "current": trips.current_trip(),
            "schema_version": request.app.state.db.schema_version(),
            "sync": "GET /api/sync?cursor=",
        },
        "health": {
            "read_only": True,
            "can_clear_codes": False,
        },
        "voice": {
            "intents": voice.supported(),
            "followup_timeout_s": voice.session.timeout_s,
            "auth": "local_or_bearer",
            "wake_word": False,
            "llm": False,
            "audio_feasibility_gate": "open",
        },
    }


@router.get("/api/telemetry/latest")
async def telemetry_latest(request: Request):
    sample = request.app.state.telemetry.latest
    if sample is None:
        return {
            "quality": "unavailable",
            "message": "No sample yet",
            "simulated": True,
            "label": "SIMULATED",
        }
    data = sample.model_dump(mode="json")
    data["label"] = "SIMULATED" if sample.simulated else "LIVE"
    return data


@router.get("/api/trips")
async def list_trips(request: Request):
    trips = request.app.state.trips.list_trips()
    return {
        "trips": trips,
        "count": len(trips),
        "simulated": True,
        "source": "sqlite",
        "note": "Trip journal from SQLite — SIMULATED provider, not a real vehicle",
    }


@router.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str, request: Request):
    trip = request.app.state.trips.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/api/sync")
async def sync(
    request: Request,
    cursor: Optional[str] = None,
    limit: int = 50,
):
    try:
        return request.app.state.trips.sync(cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/health")
async def health(request: Request):
    return request.app.state.health.status()


@router.get("/api/maintenance")
async def maintenance(request: Request):
    return request.app.state.health.maintenance()


@router.get("/api/voice/briefing")
async def voice_briefing(request: Request):
    """Startup briefing from fuel + health. No previous-trip fuel cost."""
    return request.app.state.voice.briefing()


@router.get("/api/voice/session")
async def voice_session(request: Request):
    snap = request.app.state.voice.session.snapshot()
    return {
        "session": snap.to_api(),
        "supported_intents": request.app.state.voice.supported(),
        "followup_timeout_s": request.app.state.voice.session.timeout_s,
        "audio_feasibility_gate": "open",
        "note": (
            "Follow-up context lasts ~15s after a reply. "
            "PWA TTS / background audio is unproven — gate remains open."
        ),
    }


@router.post("/api/voice/command")
async def voice_command(
    body: VoiceCommand,
    request: Request,
    _auth: dict = Depends(require_voice_access),
):
    """Authenticated-or-local voice command. Allowlisted intents only — never shell."""
    result = request.app.state.voice.handle(body.intent, body.text)
    result["auth"] = _auth
    return result


def _simulator(request: Request) -> SimulatorProvider:
    provider = request.app.state.telemetry.provider
    if not isinstance(provider, SimulatorProvider):
        raise HTTPException(status_code=400, detail="Scenario controls require the simulator provider")
    return provider


@router.get("/api/simulator/scenario")
async def get_scenario(request: Request):
    return _simulator(request).scenario()


@router.post("/api/simulator/scenario")
async def set_scenario(body: ScenarioBody, request: Request):
    try:
        return _simulator(request).set_scenario(body.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    svc = websocket.app.state.telemetry
    await svc.register(websocket)
    try:
        while True:
            # Keep alive; clients may send pings as text
            await websocket.receive_text()
    except WebSocketDisconnect:
        svc.unregister(websocket)
    except Exception:
        svc.unregister(websocket)
