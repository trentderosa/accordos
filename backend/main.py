"""AccordOS FastAPI application entrypoint."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Allow `python -m backend.main` and imports of simulator/ from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.routes import router  # noqa: E402
from backend.health import HealthService  # noqa: E402
from backend.storage import Database  # noqa: E402
from backend.telemetry import TelemetryService  # noqa: E402
from backend.trips import TripService  # noqa: E402
from backend.voice import VoiceService  # noqa: E402
from simulator import SimulatorProvider  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    await app.state.telemetry.start()
    yield
    await app.state.telemetry.stop()
    app.state.db.close()


def create_app(provider=None) -> FastAPI:
    app = FastAPI(
        title="AccordOS",
        version="0.1.0",
        description="Phase 1 simulator-backed vehicle platform API",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.db = Database()
    app.state.db.connect()
    app.state.trips = TripService()
    app.state.health = HealthService()
    app.state.voice = VoiceService()
    app.state.telemetry = TelemetryService(provider or SimulatorProvider())
    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "app": "AccordOS",
            "phase": 1,
            "docs": "/docs",
            "ws": "/ws/telemetry",
            "note": "SIMULATED telemetry — not a real vehicle",
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        app_dir=str(ROOT),
    )


if __name__ == "__main__":
    run()
