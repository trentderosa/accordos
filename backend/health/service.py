"""Read-only vehicle health — codes, trends, maintenance. Never clears DTCs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from backend.telemetry.models import TelemetrySample

from .models import (
    DiagnosticCode,
    HealthAlert,
    HealthStatus,
    MaintenanceReminder,
    MaintenanceStatus,
    TelemetryTrend,
    TrendPoint,
)
from .repository import HealthRepository
from .thresholds import THRESHOLDS, next_status, status_message


class DtcReadable(Protocol):
    def read_dtcs(self) -> list[str]: ...


class HealthService:
    """SQLite-backed health core.

    Safety invariants:
    - Read-only diagnostics only
    - Never clear codes, reset ECUs, or issue control commands
    - Distinguish codes from confirmed diagnoses in every payload
    """

    # Downsample trend inserts so SQLite stays light on Pi-class hardware.
    TREND_SAMPLE_MIN_INTERVAL_S = 5.0

    def __init__(
        self,
        repo: HealthRepository,
        *,
        dtc_provider: Optional[DtcReadable] = None,
        simulated: bool = True,
    ) -> None:
        self.repo = repo
        self._dtc_provider = dtc_provider
        self._simulated = simulated
        self._last_trend_ts: dict[str, float] = {}
        self._baseline: dict[str, float] = {}
        self.repo.seed_maintenance_if_empty()

    def bind_dtc_provider(self, provider: Optional[DtcReadable]) -> None:
        self._dtc_provider = provider

    def ingest(self, sample: TelemetrySample) -> None:
        """Observe telemetry for trends and refresh DTCs from the provider."""
        self._refresh_dtcs_from_provider()
        if sample.quality == "unavailable":
            return
        self._ingest_metric("coolant_c", sample.coolant_c, sample.timestamp)
        self._ingest_metric("voltage_v", sample.voltage_v, sample.timestamp)

    def _refresh_dtcs_from_provider(self) -> None:
        provider = self._dtc_provider
        if provider is None or not hasattr(provider, "read_dtcs"):
            return
        try:
            codes = list(provider.read_dtcs())
        except Exception:  # noqa: BLE001 — health must not kill telemetry
            return
        source = getattr(provider, "name", "unknown")
        simulated = bool(getattr(provider, "name", "") == "simulator" or self._simulated)
        self.repo.upsert_active_dtcs(codes, source=source, simulated=simulated)

    def _ingest_metric(
        self,
        metric: str,
        value: Optional[float],
        ts: datetime,
    ) -> None:
        if value is None or metric not in THRESHOLDS:
            return
        threshold = THRESHOLDS[metric]
        mono = ts.timestamp() if ts.tzinfo else ts.replace(tzinfo=timezone.utc).timestamp()
        last = self._last_trend_ts.get(metric, 0.0)
        if mono - last < self.TREND_SAMPLE_MIN_INTERVAL_S:
            # Still evaluate thresholds on every sample for responsiveness.
            pass
        else:
            self.repo.insert_trend_sample(metric, value, ts)
            self._last_trend_ts[metric] = mono

        if metric not in self._baseline:
            self._baseline[metric] = value
        else:
            # Slow EMA toward recent values for a soft baseline.
            self._baseline[metric] = (0.98 * self._baseline[metric]) + (0.02 * value)

        previous = self.repo.get_trend_state(metric)
        if previous == "unavailable":
            previous = "ok"
        status = next_status(threshold, value, previous)
        message = status_message(threshold, status)
        self.repo.set_trend_state(
            metric,
            status,
            latest=value,
            baseline=round(self._baseline[metric], 2),
            message=message,
        )

        alert_id = f"trend:{metric}"
        if status == "alert":
            self.repo.record_alert_event(
                alert_id,
                severity="critical" if metric == "coolant_c" else "warning",
                title=f"{threshold.label} alert",
                detail=message,
                metric=metric,
                active=True,
                simulated=self._simulated,
            )
        elif status == "watch":
            self.repo.record_alert_event(
                alert_id,
                severity="warning",
                title=f"{threshold.label} watch",
                detail=message,
                metric=metric,
                active=True,
                simulated=self._simulated,
            )
        else:
            self.repo.record_alert_event(
                alert_id,
                severity="info",
                title=f"{threshold.label} normal",
                detail=message,
                metric=metric,
                active=False,
                simulated=self._simulated,
            )

    def status(self) -> dict[str, Any]:
        self._refresh_dtcs_from_provider()
        dtc_rows = self.repo.list_dtcs(include_historical=True)
        dtcs = [DiagnosticCode(**row) for row in dtc_rows]
        active = [d for d in dtcs if d.status == "active"]

        trends: list[TelemetryTrend] = []
        for metric, threshold in THRESHOLDS.items():
            points_raw = self.repo.recent_trend_samples(metric, limit=36)
            state = self.repo.get_trend_state(metric)
            latest = points_raw[-1][1] if points_raw else None
            baseline = self._baseline.get(metric)
            trends.append(
                TelemetryTrend(
                    metric=metric,
                    unit=threshold.unit,
                    label=threshold.label,
                    latest=round(latest, 2) if latest is not None else None,
                    baseline=round(baseline, 2) if baseline is not None else None,
                    status=state,
                    message=status_message(threshold, state),
                    points=[
                        TrendPoint(ts=ts, value=round(val, 2)) for ts, val in points_raw
                    ],
                    hysteresis_note=(
                        f"Watch {threshold.watch}{threshold.unit}; "
                        f"alert {threshold.alert}{threshold.unit}; "
                        f"clears with hysteresis."
                    ),
                )
            )

        # Active DTC alert (deduped) so the UI has a single health banner source.
        if active:
            codes = ", ".join(d.code for d in active)
            self.repo.record_alert_event(
                "dtc:active",
                severity="critical"
                if any(d.severity == "critical" for d in active)
                else "warning",
                title="Diagnostic codes present",
                detail=(
                    f"Active codes: {codes}. Codes are not confirmed diagnoses. "
                    "Factory warnings remain authoritative. AccordOS never clears codes."
                ),
                metric=None,
                active=True,
                simulated=self._simulated,
            )
        else:
            self.repo.record_alert_event(
                "dtc:active",
                severity="info",
                title="No active diagnostic codes",
                detail="No active codes reported — absence of codes is not a clean bill of health.",
                metric=None,
                active=False,
                simulated=self._simulated,
            )

        alerts = [HealthAlert(**row) for row in self.repo.list_active_alerts()]
        payload = HealthStatus(
            dtcs=dtcs,
            alerts=alerts,
            trends=trends,
            active_dtc_count=len(active),
            read_only=True,
            can_clear_codes=False,
            simulated=self._simulated,
            schema_version=self.repo.db.schema_version(),
        )
        return payload.model_dump(mode="json")

    def maintenance(self) -> dict[str, Any]:
        reminders = [
            MaintenanceReminder(**row) for row in self.repo.list_maintenance()
        ]
        payload = MaintenanceStatus(
            reminders=reminders,
            simulated=self._simulated,
        )
        return payload.model_dump(mode="json")
