"""Unit tests for the read-only PID / metric allowlist."""

from __future__ import annotations

from backend.telemetry.allowlist import (
    ALLOWLISTED_PIDS,
    FORBIDDEN_MODES,
    UNSUPPORTED_METRICS,
    allowlisted_metrics,
    allowlisted_pid_codes,
    capability_snapshot,
    filter_requested_pids,
    get_pid,
    is_metric_allowed,
    is_metric_unsupported,
    is_mode_forbidden,
    is_pid_allowed,
)


def test_core_pids_are_allowlisted():
    assert is_pid_allowed("010C")  # RPM
    assert is_pid_allowed("010d")  # case-insensitive
    assert is_pid_allowed("010D")  # speed
    assert is_pid_allowed("03")  # DTC read
    assert not is_pid_allowed("010A")  # not on list
    assert not is_pid_allowed("04")  # clear — forbidden path


def test_forbidden_clear_mode():
    assert is_mode_forbidden(0x04)
    assert 0x04 in FORBIDDEN_MODES
    assert not is_mode_forbidden(0x01)


def test_unsupported_metrics_honest():
    assert is_metric_unsupported("odometer")
    assert is_metric_unsupported("oil_life")
    assert is_metric_unsupported("tire_pressure")
    assert not is_metric_allowed("odometer")
    assert is_metric_allowed("rpm")


def test_filter_requested_pids_classifies():
    result = filter_requested_pids(["010C", "04", "0199", "010D"])
    assert result["010C"] == "allowed"
    assert result["010D"] == "allowed"
    assert result["04"] == "forbidden"
    assert result["0199"] == "unavailable"


def test_capability_snapshot_marks_unsupported_unavailable():
    caps = capability_snapshot(
        supported_metrics=["rpm", "speed_mph"],
        provider="test",
        simulated=False,
    )
    assert caps["read_only"] is True
    assert caps["can_clear_codes"] is False
    assert caps["can_write"] is False
    assert "rpm" in caps["metrics"]
    assert "fuel_level_pct" in caps["unavailable_metrics"]
    assert caps["pid_status"]["010C"] == "available"
    assert caps["pid_status"]["012F"] == "unavailable"
    assert "odometer" in caps["unsupported"]
    assert set(UNSUPPORTED_METRICS).issubset(set(caps["unsupported"]))


def test_allowlist_helpers_cover_entries():
    assert len(ALLOWLISTED_PIDS) >= 6
    assert allowlisted_pid_codes() == [e.pid for e in ALLOWLISTED_PIDS]
    assert "rpm" in allowlisted_metrics()
    assert get_pid("0142") is not None
    assert get_pid("0142").metric == "voltage_v"
