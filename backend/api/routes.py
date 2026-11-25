"""REST + WebSocket routes matching handoff §12."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

router = APIRouter()


class VoiceCommand(BaseModel):
    intent: str = Field(..., min_length=1, max_length=64)
    text: Optional[str] = Field(default=None, max_length=256)


@router.get("/api/capabilities")
async def capabilities(request: Request):
    svc = request.app.state.telemetry
    return svc.provider.capabilities()


@router.get("/api/status")
async def status(request: Request):
    svc = request.app.state.telemetry
    return {
        "app": "AccordOS",
        "phase": 1,
        "api_version": "0.1.0",
        "connection": svc.connection_status,
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
    return {"trips": request.app.state.trips.list_trips(), "simulated": True}


@router.get("/api/trips/{trip_id}")
async def get_trip(trip_id: str, request: Request):
    trip = request.app.state.trips.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/api/sync")
async def sync(request: Request, cursor: Optional[str] = None):
    return request.app.state.trips.sync(cursor)


@router.get("/api/health")
async def health(request: Request):
    return request.app.state.health.status()


@router.get("/api/maintenance")
async def maintenance(request: Request):
    return request.app.state.health.maintenance()


@router.post("/api/voice/command")
async def voice_command(body: VoiceCommand, request: Request):
    return request.app.state.voice.handle(body.intent, body.text)


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
