"""Driving efficiency score scaffold.

This is an efficiency indicator, not a safety assessment. Scores are withheld
when sampling coverage or confidence is too low. Never discourages necessary
braking or rewards unsafe behavior.
"""

from __future__ import annotations

import json
from typing import Optional

from .models import (
    EFFICIENCY_WEIGHTS,
    EfficiencyResult,
    EfficiencyStatus,
)
from .state_machine import OpenTrip

# Minimum samples / distance before we attempt a score
MIN_SAMPLES = 20
MIN_DISTANCE_MI = 0.15
MIN_CONFIDENCE = 0.45

# Soft thresholds for smooth accel/decel (mph/s) — scaffold only, not calibrated
HARD_ACCEL_MPH_S = 6.0
HARD_BRAKE_MPH_S = -7.0


def score_trip(trip: OpenTrip) -> EfficiencyResult:
    """Compute a provisional efficiency score or withhold with explanation."""
    weights = dict(EFFICIENCY_WEIGHTS)
    subscores: dict[str, Optional[float]] = {
        "smooth_acceleration": None,
        "smooth_deceleration": None,
        "fuel_efficiency": None,
        "engine_efficiency": None,
        "idling_efficiency": None,
    }
    coverage: dict[str, float] = {
        "samples": float(trip.sample_count),
        "distance_mi": round(trip.distance_mi, 4),
        "accel_events": float(len(trip.accel_events)),
    }

    if trip.sample_count < MIN_SAMPLES or trip.distance_mi < MIN_DISTANCE_MI:
        return EfficiencyResult(
            score=None,
            confidence=0.0,
            status=EfficiencyStatus.WITHHELD,
            weights=weights,
            subscores=subscores,
            coverage=coverage,
            explanation=(
                "Efficiency score withheld — not enough trip distance or samples "
                "for a fair estimate. This is not a safety rating."
            ),
        )

    accel = [a for a in trip.accel_events if a > 0.3]
    decel = [a for a in trip.accel_events if a < -0.3]

    if accel:
        hard = sum(1 for a in accel if a >= HARD_ACCEL_MPH_S)
        subscores["smooth_acceleration"] = max(0.0, 100.0 * (1.0 - hard / len(accel)))
        coverage["accel_coverage"] = len(accel) / max(1, len(trip.accel_events))
    else:
        coverage["accel_coverage"] = 0.0

    if decel:
        hard = sum(1 for a in decel if a <= HARD_BRAKE_MPH_S)
        # Necessary hard braking is not penalized as "unsafe" messaging —
        # we only track smoothness coverage for the efficiency indicator.
        subscores["smooth_deceleration"] = max(0.0, 100.0 * (1.0 - hard / len(decel)))
        coverage["decel_coverage"] = len(decel) / max(1, len(trip.accel_events))
    else:
        coverage["decel_coverage"] = 0.0

    # Fuel efficiency: only when fuel delta is usable
    if (
        trip.fuel_start_pct is not None
        and trip.fuel_end_pct is not None
        and trip.distance_mi >= 0.5
    ):
        used = trip.fuel_start_pct - trip.fuel_end_pct
        if used > 0.05:
            # Scaffold: lower %/mi is better; map into 0–100 loosely
            pct_per_mi = used / trip.distance_mi
            subscores["fuel_efficiency"] = max(0.0, min(100.0, 100.0 - pct_per_mi * 40.0))
            coverage["fuel"] = 1.0
        else:
            coverage["fuel"] = 0.2
    else:
        coverage["fuel"] = 0.0

    # Engine efficiency / idling — coarse scaffolds from idle ratio
    duration = 0.0
    if trip.end_ts and trip.start_ts:
        duration = max(0.0, (trip.end_ts - trip.start_ts).total_seconds())
    elif trip.last_ts and trip.start_ts:
        duration = max(0.0, (trip.last_ts - trip.start_ts).total_seconds())

    if duration > 0:
        idle_ratio = trip.idle_time_s / duration
        subscores["idling_efficiency"] = max(0.0, min(100.0, 100.0 * (1.0 - idle_ratio)))
        coverage["idle"] = 1.0
        # Without load/MAF calibration, engine efficiency stays low-confidence
        if trip.moving_time_s > 0:
            subscores["engine_efficiency"] = max(
                0.0, min(100.0, 100.0 - idle_ratio * 50.0)
            )
            coverage["engine"] = 0.4
        else:
            coverage["engine"] = 0.0
    else:
        coverage["idle"] = 0.0
        coverage["engine"] = 0.0

    # Weighted average over available categories only
    available = [(k, v) for k, v in subscores.items() if v is not None]
    if not available:
        return EfficiencyResult(
            score=None,
            confidence=0.0,
            status=EfficiencyStatus.WITHHELD,
            weights=weights,
            subscores=subscores,
            coverage=coverage,
            explanation=(
                "Efficiency score withheld — no category had enough trustworthy "
                "inputs. This indicator is not a safety assessment."
            ),
        )

    weight_sum = sum(weights[k] for k, _ in available)
    score = sum(subscores[k] * weights[k] for k, _ in available) / weight_sum

    # Confidence from coverage of the highest-weight categories
    cov_bits = [
        coverage.get("accel_coverage", 0.0),
        coverage.get("decel_coverage", 0.0),
        coverage.get("fuel", 0.0),
        coverage.get("engine", 0.0),
        coverage.get("idle", 0.0),
    ]
    confidence = sum(cov_bits) / len(cov_bits)
    # Penalize short / incomplete trips
    if trip.incomplete:
        confidence *= 0.5
    if trip.distance_mi < 1.0:
        confidence *= 0.75

    if confidence < MIN_CONFIDENCE:
        return EfficiencyResult(
            score=round(score, 1),
            confidence=round(confidence, 3),
            status=EfficiencyStatus.WITHHELD,
            weights=weights,
            subscores={k: (round(v, 1) if v is not None else None) for k, v in subscores.items()},
            coverage=coverage,
            explanation=(
                "Efficiency score withheld — confidence too low "
                f"({confidence:.0%}). Partial category estimates were computed "
                "for calibration only and are not shown as a trip rating. "
                "This is not a safety assessment."
            ),
        )

    return EfficiencyResult(
        score=round(score, 1),
        confidence=round(confidence, 3),
        status=EfficiencyStatus.AVAILABLE,
        weights=weights,
        subscores={k: (round(v, 1) if v is not None else None) for k, v in subscores.items()},
        coverage=coverage,
        explanation=(
            "Provisional efficiency indicator from available categories "
            f"(weights {weights}). Not a safety rating; necessary braking is "
            "never discouraged."
        ),
    )


def efficiency_to_json(result: EfficiencyResult) -> str:
    return json.dumps(result.model_dump(mode="json"))
