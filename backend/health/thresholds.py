"""Documented trend thresholds with hysteresis to reduce alert flicker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

TrendStatus = Literal["ok", "watch", "alert", "unavailable"]


@dataclass(frozen=True)
class MetricThreshold:
    metric: str
    unit: str
    label: str
    # Enter watch/alert when value crosses these (high-side unless high=False).
    watch: float
    alert: float
    # Clear back to ok only after crossing clear_watch (hysteresis).
    clear_watch: float
    clear_alert: float
    high: bool = True
    watch_message: str = ""
    alert_message: str = ""
    ok_message: str = "Within expected range for simulator baselines."


# Coolant: warm cruise ~85°C in simulator; watch above 100, alert above 108.
# Clear watch below 96, clear alert below 102.
COOLANT = MetricThreshold(
    metric="coolant_c",
    unit="°C",
    label="Coolant",
    watch=100.0,
    alert=108.0,
    clear_watch=96.0,
    clear_alert=102.0,
    high=True,
    watch_message="Coolant trending warmer than the simulator baseline.",
    alert_message="Coolant sustained above alert threshold — factory gauge takes priority.",
    ok_message="Coolant near expected warm-engine range.",
)

# Voltage: charging ~14.2V, resting ~12.4V. Low-side thresholds.
VOLTAGE = MetricThreshold(
    metric="voltage_v",
    unit="V",
    label="System voltage",
    watch=12.2,
    alert=11.8,
    clear_watch=12.5,
    clear_alert=12.1,
    high=False,
    watch_message="System voltage trending low versus charging baseline.",
    alert_message="System voltage sustained low — factory warnings take priority.",
    ok_message="System voltage near expected range.",
)

THRESHOLDS: dict[str, MetricThreshold] = {
    COOLANT.metric: COOLANT,
    VOLTAGE.metric: VOLTAGE,
}


def next_status(
    threshold: MetricThreshold,
    value: Optional[float],
    previous: TrendStatus,
) -> TrendStatus:
    if value is None:
        return "unavailable"

    if threshold.high:
        if previous == "alert":
            if value < threshold.clear_alert:
                previous = "watch" if value >= threshold.clear_watch else "ok"
            else:
                return "alert"
        if previous == "watch":
            if value >= threshold.alert:
                return "alert"
            if value < threshold.clear_watch:
                return "ok"
            return "watch"
        # ok / unavailable → evaluate fresh
        if value >= threshold.alert:
            return "alert"
        if value >= threshold.watch:
            return "watch"
        return "ok"

    # low-side
    if previous == "alert":
        if value > threshold.clear_alert:
            previous = "watch" if value <= threshold.clear_watch else "ok"
        else:
            return "alert"
    if previous == "watch":
        if value <= threshold.alert:
            return "alert"
        if value > threshold.clear_watch:
            return "ok"
        return "watch"
    if value <= threshold.alert:
        return "alert"
    if value <= threshold.watch:
        return "watch"
    return "ok"


def status_message(threshold: MetricThreshold, status: TrendStatus) -> str:
    if status == "alert":
        return threshold.alert_message
    if status == "watch":
        return threshold.watch_message
    if status == "ok":
        return threshold.ok_message
    return "No recent samples for this metric."
