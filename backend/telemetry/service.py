"""Telemetry service: polls a provider and fans out to WebSocket clients."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional, Set

from fastapi import WebSocket

from .models import TelemetrySample
from .provider import TelemetryProvider

logger = logging.getLogger(__name__)

STALE_AFTER_S = 3.0
POLL_INTERVAL_S = 0.25

SampleListener = Callable[[TelemetrySample], None]


class TelemetryService:
    def __init__(
        self,
        provider: TelemetryProvider,
        *,
        on_sample: Optional[SampleListener] = None,
    ) -> None:
        self.provider = provider
        self._on_sample = on_sample
        self._latest: Optional[TelemetrySample] = None
        self._clients: Set[WebSocket] = set()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._connected = False
        self._last_error: Optional[str] = None

    @property
    def latest(self) -> Optional[TelemetrySample]:
        if self._latest is None:
            return None
        return self._latest.with_stale_if_needed(STALE_AFTER_S)

    @property
    def connection_status(self) -> dict:
        sample = self.latest
        age = sample.age_seconds() if sample else None
        return {
            "provider": self.provider.name,
            "provider_connected": self._connected and self.provider.is_connected(),
            "streaming": self._running,
            "clients": len(self._clients),
            "sample_age_s": age,
            "stale": bool(sample and sample.quality == "stale"),
            "last_error": self._last_error,
            "simulated": self.provider.name == "simulator",
        }

    async def start(self) -> None:
        if self._running:
            return
        await self.provider.connect()
        self._connected = True
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="telemetry-poll")
        logger.info("TelemetryService started with provider=%s", self.provider.name)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.provider.disconnect()
        self._connected = False

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        if self._latest:
            await ws.send_json(self._payload(self._latest))

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                sample = await self.provider.read()
                self._latest = sample
                self._last_error = None
                self._notify(sample)
                await self._broadcast(sample)
            except Exception as exc:  # noqa: BLE001 — surface to clients
                self._last_error = str(exc)
                logger.exception("Telemetry poll failed")
                self._latest = TelemetrySample(
                    quality="unavailable",
                    timestamp=datetime.now(timezone.utc),
                    message=str(exc),
                    simulated=self.provider.name == "simulator",
                )
                self._notify(self._latest)
            await asyncio.sleep(POLL_INTERVAL_S)

    def _notify(self, sample: TelemetrySample) -> None:
        if self._on_sample is None:
            return
        try:
            self._on_sample(sample)
        except Exception:  # noqa: BLE001 — trip journal must not kill telemetry
            logger.exception("Trip sample listener failed")

    async def _broadcast(self, sample: TelemetrySample) -> None:
        if not self._clients:
            return
        payload = self._payload(sample)
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.unregister(ws)

    @staticmethod
    def _payload(sample: TelemetrySample) -> dict:
        data = sample.model_dump(mode="json")
        data["label"] = "SIMULATED" if sample.simulated else "LIVE"
        return data
