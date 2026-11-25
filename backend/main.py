"""AccordOS FastAPI application entrypoint."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Allow `python -m backend.main` and imports of simulator/ from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.routes import router  # noqa: E402
from backend.health import HealthRepository, HealthService  # noqa: E402
from backend.storage import Database  # noqa: E402
from backend.telemetry import TelemetryService  # noqa: E402
from backend.telemetry.models import TelemetrySample  # noqa: E402
from backend.trips import TripService  # noqa: E402
from backend.voice import VoiceService  # noqa: E402
from simulator import SimulatorProvider  # noqa: E402

# Phase 1 LAN dev: localhost + RFC1918 private IPs only.
# Do NOT expose this API to the public internet.
LAN_ORIGIN_REGEX = (
    r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
    r")(:\d+)?$"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await app.state.telemetry.start()
    yield
    await app.state.telemetry.stop()
    app.state.db.close()


def _default_db_path() -> Optional[Path]:
    """On-disk DB for normal runs; None (in-memory) when ACCORDOS_DB=:memory:."""
    raw = os.environ.get("ACCORDOS_DB")
    if raw == ":memory:":
        return None
    if raw:
        return Path(raw)
    return ROOT / "data" / "accordos.db"


def create_app(provider=None, *, db: Optional[Database] = None) -> FastAPI:
    app = FastAPI(
        title="AccordOS",
        version="0.4.0",
        description="Simulator-backed vehicle platform with trip intelligence and health core",
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
        allow_origin_regex=LAN_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    active_provider = provider or SimulatorProvider()
    app.state.db = db if db is not None else Database(_default_db_path())
    app.state.db.connect()
    app.state.trips = TripService(app.state.db, recover_on_start=True)
    app.state.health = HealthService(
        HealthRepository(app.state.db),
        dtc_provider=active_provider,
        simulated=True,
    )
    app.state.voice = VoiceService()

    def _on_sample(sample: TelemetrySample) -> None:
        app.state.trips.ingest(sample)
        app.state.health.ingest(sample)

    app.state.telemetry = TelemetryService(
        active_provider,
        on_sample=_on_sample,
    )
    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "app": "AccordOS",
            "phase": 4,
            "phase_note": (
                "Health core on simulator (Phase 4 partial — voice still stub); "
                "Pi hardware still Phase 2"
            ),
            "api_version": "0.4.0",
            "docs": "/docs",
            "ws": "/ws/telemetry",
            "note": "SIMULATED telemetry — not a real vehicle",
            "lan": (
                "Bind with ACCORDOS_HOST=0.0.0.0 for same-LAN iPhone access. "
                "Local network only — not for public internet."
            ),
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    # Default 0.0.0.0 so iPhone on the same LAN can reach the Mac.
    # Override with ACCORDOS_HOST=127.0.0.1 to lock to loopback.
    # SECURITY: local / trusted network only — do not port-forward or expose publicly.
    host = os.environ.get("ACCORDOS_HOST", "0.0.0.0")
    port = int(os.environ.get("ACCORDOS_PORT", "8000"))

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=False,
        app_dir=str(ROOT),
    )


if __name__ == "__main__":
    run()
