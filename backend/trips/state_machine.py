"""Trip state machine: idle → starting → active → ending → finalized/recovered.

Engine-running evidence uses RPM + communication quality. A trip never ends
solely because speed is zero (stopped traffic / idle at a light).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.telemetry.models import TelemetrySample, VehicleMode

from .models import TripState

# Debounce windows (seconds of sustained evidence)
ENGINE_ON_DEBOUNCE_S = 1.5
ENGINE_OFF_DEBOUNCE_S = 3.0

# RPM thresholds — conservative for simulator + typical gasoline idle
RPM_RUNNING_MIN = 400.0
RPM_OFF_MAX = 200.0

# Speed near zero still counts as idle (not trip end)
IDLE_SPEED_MAX_MPH = 0.5

# Persist a checkpoint at least this often while a trip is open
CHECKPOINT_INTERVAL_S = 2.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


@dataclass
class OpenTrip:
    """In-memory working set for a trip that is not yet finalized."""

    id: str
    state: TripState
    start_ts: datetime
    end_ts: Optional[datetime] = None
    distance_mi: float = 0.0
    max_speed_mph: float = 0.0
    idle_time_s: float = 0.0
    moving_time_s: float = 0.0
    speed_time_integral: float = 0.0  # sum(speed * dt) for avg while moving
    fuel_start_pct: Optional[float] = None
    fuel_end_pct: Optional[float] = None
    last_ts: Optional[datetime] = None
    last_speed: Optional[float] = None
    sample_count: int = 0
    communicating_loss_s: float = 0.0
    incomplete: bool = False
    simulated: bool = True
    source: str = "simulator"
    checkpoint_seq: int = 0
    last_checkpoint_at: Optional[datetime] = None
    # Recent speed deltas for efficiency scaffold (mph/s samples)
    accel_events: list[float] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class EngineEvidence:
    running: bool
    communicating: bool
    parked_explicit: bool


def classify_engine(sample: TelemetrySample) -> EngineEvidence:
    communicating = sample.quality in ("good", "estimated", "stale")
    rpm = sample.rpm
    parked_explicit = sample.mode == VehicleMode.PARKED

    if not communicating or rpm is None:
        # No trustworthy RPM — do not claim engine running or off.
        return EngineEvidence(
            running=False, communicating=False, parked_explicit=parked_explicit
        )

    if rpm >= RPM_RUNNING_MIN:
        return EngineEvidence(
            running=True, communicating=True, parked_explicit=False
        )

    if rpm <= RPM_OFF_MAX or parked_explicit:
        return EngineEvidence(
            running=False, communicating=True, parked_explicit=parked_explicit
        )

    # Ambiguous band — treat as not clearly running
    return EngineEvidence(
        running=False, communicating=True, parked_explicit=parked_explicit
    )


@dataclass
class TransitionResult:
    """Outcome of ingesting one sample into the state machine."""

    trip: Optional[OpenTrip]
    opened: bool = False
    closed: bool = False
    recovered: bool = False
    checkpoint_due: bool = False
    sample_recorded: bool = False
    previous_state: Optional[TripState] = None


class TripStateMachine:
    def __init__(
        self,
        *,
        engine_on_debounce_s: float = ENGINE_ON_DEBOUNCE_S,
        engine_off_debounce_s: float = ENGINE_OFF_DEBOUNCE_S,
    ) -> None:
        self.engine_on_debounce_s = engine_on_debounce_s
        self.engine_off_debounce_s = engine_off_debounce_s
        self.state = TripState.IDLE
        self.open: Optional[OpenTrip] = None
        self._on_since: Optional[datetime] = None
        self._off_since: Optional[datetime] = None

    def ingest(self, sample: TelemetrySample) -> TransitionResult:
        evidence = classify_engine(sample)
        ts = _as_utc(sample.timestamp)
        prev = self.state
        result = TransitionResult(trip=self.open, previous_state=prev)

        if self.state == TripState.IDLE:
            self._handle_idle(ts, evidence, sample, result)
        elif self.state == TripState.STARTING:
            self._handle_starting(ts, evidence, sample, result)
        elif self.state == TripState.ACTIVE:
            self._handle_active(ts, evidence, sample, result)
        elif self.state == TripState.ENDING:
            self._handle_ending(ts, evidence, sample, result)
        # finalized/recovered are terminal for the open trip; machine returns to idle

        # Keep the closed trip on the result; only refresh from open when still in-progress.
        if not result.closed:
            result.trip = self.open
            if self.open and result.sample_recorded:
                result.checkpoint_due = self._checkpoint_due(ts)
        return result

    def force_recover_open(self, *, reason: str = "Interrupted trip recovered after shutdown") -> Optional[OpenTrip]:
        """Finalize an open trip as recovered (power-loss / process restart)."""
        if self.open is None:
            return None
        trip = self.open
        trip.state = TripState.RECOVERED
        trip.incomplete = True
        trip.note = reason
        trip.end_ts = trip.last_ts or trip.start_ts
        self.state = TripState.IDLE
        self.open = None
        self._on_since = None
        self._off_since = None
        return trip

    def _handle_idle(
        self,
        ts: datetime,
        evidence: EngineEvidence,
        sample: TelemetrySample,
        result: TransitionResult,
    ) -> None:
        if evidence.running and evidence.communicating:
            if self._on_since is None:
                self._on_since = ts
            on_for = (ts - self._on_since).total_seconds()
            if on_for >= self.engine_on_debounce_s:
                trip = self._open_trip(sample, ts)
                self.open = trip
                self.state = TripState.STARTING
                trip.state = TripState.STARTING
                result.opened = True
                result.sample_recorded = True
                self._accumulate(trip, sample, ts, evidence)
                # Promote quickly once we have motion or sustained running
                if (sample.speed_mph or 0) > IDLE_SPEED_MAX_MPH:
                    self.state = TripState.ACTIVE
                    trip.state = TripState.ACTIVE
                self._off_since = None
        else:
            self._on_since = None

    def _handle_starting(
        self,
        ts: datetime,
        evidence: EngineEvidence,
        sample: TelemetrySample,
        result: TransitionResult,
    ) -> None:
        assert self.open is not None
        result.sample_recorded = True
        self._accumulate(self.open, sample, ts, evidence)

        if evidence.running and evidence.communicating:
            self._off_since = None
            # Enter active once moving, or after a bit more sustained running
            if (sample.speed_mph or 0) > IDLE_SPEED_MAX_MPH:
                self.state = TripState.ACTIVE
                self.open.state = TripState.ACTIVE
            elif self._on_since and (ts - self._on_since).total_seconds() >= (
                self.engine_on_debounce_s + 1.0
            ):
                self.state = TripState.ACTIVE
                self.open.state = TripState.ACTIVE
        elif evidence.communicating and not evidence.running:
            if self._off_since is None:
                self._off_since = ts
            if (ts - self._off_since).total_seconds() >= self.engine_off_debounce_s:
                self._finalize(result, recovered=False)
        # Loss of communication during starting: stay in starting, do not end

    def _handle_active(
        self,
        ts: datetime,
        evidence: EngineEvidence,
        sample: TelemetrySample,
        result: TransitionResult,
    ) -> None:
        assert self.open is not None
        result.sample_recorded = True
        self._accumulate(self.open, sample, ts, evidence)

        if evidence.running and evidence.communicating:
            self._off_since = None
            return

        if not evidence.communicating:
            # Keep trip active across disconnect — never end on silence alone
            self._off_since = None
            return

        # Communicating + not running → begin ending debounce
        # Explicitly ignore speed==0 as an end signal (idle traffic).
        if self._off_since is None:
            self._off_since = ts
            self.state = TripState.ENDING
            self.open.state = TripState.ENDING
        elif (ts - self._off_since).total_seconds() >= self.engine_off_debounce_s:
            self._finalize(result, recovered=False)

    def _handle_ending(
        self,
        ts: datetime,
        evidence: EngineEvidence,
        sample: TelemetrySample,
        result: TransitionResult,
    ) -> None:
        assert self.open is not None
        result.sample_recorded = True
        self._accumulate(self.open, sample, ts, evidence)

        if evidence.running and evidence.communicating:
            # False alarm — back to active (e.g. stop-start traffic)
            self._off_since = None
            self.state = TripState.ACTIVE
            self.open.state = TripState.ACTIVE
            return

        if not evidence.communicating:
            # Lost link while ending — return to active and wait
            self._off_since = None
            self.state = TripState.ACTIVE
            self.open.state = TripState.ACTIVE
            return

        if self._off_since is None:
            self._off_since = ts
        if (ts - self._off_since).total_seconds() >= self.engine_off_debounce_s:
            self._finalize(result, recovered=False)

    def _finalize(self, result: TransitionResult, *, recovered: bool) -> None:
        assert self.open is not None
        trip = self.open
        trip.end_ts = trip.last_ts or _utc_now()
        if recovered:
            trip.state = TripState.RECOVERED
            trip.incomplete = True
            result.recovered = True
        else:
            trip.state = TripState.FINALIZED
        result.closed = True
        result.trip = trip
        self.open = None
        self.state = TripState.IDLE
        self._on_since = None
        self._off_since = None

    def _open_trip(self, sample: TelemetrySample, ts: datetime) -> OpenTrip:
        return OpenTrip(
            id=str(uuid4()),
            state=TripState.STARTING,
            start_ts=ts,
            last_ts=ts,
            last_speed=sample.speed_mph,
            fuel_start_pct=sample.fuel_level_pct,
            fuel_end_pct=sample.fuel_level_pct,
            simulated=bool(sample.simulated),
            source=sample.source,
            last_checkpoint_at=ts,
        )

    def _accumulate(
        self,
        trip: OpenTrip,
        sample: TelemetrySample,
        ts: datetime,
        evidence: EngineEvidence,
    ) -> None:
        dt = 0.0
        if trip.last_ts is not None:
            dt = max(0.0, (ts - trip.last_ts).total_seconds())

        speed = sample.speed_mph
        if speed is None:
            speed = trip.last_speed if trip.last_speed is not None else 0.0

        if dt > 0 and dt < 30.0:  # ignore huge gaps as continuous motion
            # Integrate distance from speed (mph → miles)
            trip.distance_mi += (speed * dt) / 3600.0
            if speed > IDLE_SPEED_MAX_MPH:
                trip.moving_time_s += dt
                trip.speed_time_integral += speed * dt
            elif evidence.running:
                trip.idle_time_s += dt
            if not evidence.communicating:
                trip.communicating_loss_s += dt

            # Accel events for efficiency scaffold
            if trip.last_speed is not None:
                accel = (speed - trip.last_speed) / dt  # mph/s
                trip.accel_events.append(accel)
                if len(trip.accel_events) > 5000:
                    trip.accel_events = trip.accel_events[-2500:]

        if sample.speed_mph is not None:
            trip.max_speed_mph = max(trip.max_speed_mph, sample.speed_mph)
            trip.last_speed = sample.speed_mph

        if sample.fuel_level_pct is not None:
            if trip.fuel_start_pct is None:
                trip.fuel_start_pct = sample.fuel_level_pct
            trip.fuel_end_pct = sample.fuel_level_pct

        trip.last_ts = ts
        trip.sample_count += 1
        trip.state = self.state if self.state not in (TripState.IDLE,) else trip.state

    def _checkpoint_due(self, ts: datetime) -> bool:
        if self.open is None:
            return False
        if self.open.last_checkpoint_at is None:
            return True
        return (ts - self.open.last_checkpoint_at).total_seconds() >= CHECKPOINT_INTERVAL_S

    def mark_checkpoint(self, ts: Optional[datetime] = None) -> None:
        if self.open is None:
            return
        self.open.checkpoint_seq += 1
        self.open.last_checkpoint_at = ts or _utc_now()
