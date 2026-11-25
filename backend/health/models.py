"""Health and maintenance API models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DiagnosticCode(BaseModel):
    code: str
    title: str
    summary: str
    common_causes: list[str] = Field(default_factory=list)
    interpretation: Literal["code"] = "code"
    interpretation_note: str
    severity: Literal["info", "warning", "critical"] = "info"
    system: str = "unknown"
    reference_found: bool = False
    status: Literal["active", "historical"] = "active"
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source: str = "simulator"
    simulated: bool = True


class TrendPoint(BaseModel):
    ts: datetime
    value: float


class TelemetryTrend(BaseModel):
    metric: str
    unit: str
    label: str
    latest: Optional[float] = None
    baseline: Optional[float] = None
    status: Literal["ok", "watch", "alert", "unavailable"] = "unavailable"
    message: str
    points: list[TrendPoint] = Field(default_factory=list)
    hysteresis_note: Optional[str] = None


class HealthAlert(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str
    metric: Optional[str] = None
    active: bool = True
    simulated: bool = True


class MaintenanceReminder(BaseModel):
    id: str
    title: str
    kind: str
    due_label: str
    interval_mi: Optional[float] = None
    interval_months: Optional[int] = None
    last_service_label: Optional[str] = None
    status: Literal["upcoming", "due_soon", "overdue", "unknown"] = "unknown"
    note: Optional[str] = None
    simulated: bool = True
    source: str = "user_interval"


class HealthStatus(BaseModel):
    dtcs: list[DiagnosticCode] = Field(default_factory=list)
    alerts: list[HealthAlert] = Field(default_factory=list)
    trends: list[TelemetryTrend] = Field(default_factory=list)
    active_dtc_count: int = 0
    read_only: bool = True
    can_clear_codes: bool = False
    simulated: bool = True
    schema_version: int = 3
    disclaimer: str = (
        "Diagnostic codes are stored fault flags — not confirmed diagnoses. "
        "Factory instrument warnings remain authoritative. AccordOS never clears codes."
    )
    note: str = "SIMULATED health — not a real vehicle scan"


class MaintenanceStatus(BaseModel):
    reminders: list[MaintenanceReminder] = Field(default_factory=list)
    simulated: bool = True
    note: str = (
        "Reminders use user-provided intervals / known service labels — "
        "not fabricated odometer readings."
    )
    extras: dict[str, Any] = Field(default_factory=dict)
