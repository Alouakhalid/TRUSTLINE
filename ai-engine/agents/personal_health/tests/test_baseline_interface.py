"""Test suite verifying PersonalBaselineInterface statuses, provenance, and guards."""
import pytest
from personal_health.services.baseline_interface import PersonalBaselineInterface
from personal_health.schemas.assessment import BaselineStatus

def test_01_baseline_status_not_available_default():
    """Verify default status is NOT_AVAILABLE with no deviation calculation."""
    svc = PersonalBaselineInterface()
    assert svc.get_baseline_status("ASTRO-01") == BaselineStatus.NOT_AVAILABLE
    assert svc.is_baseline_available("ASTRO-01") is False

    dev = svc.evaluate_deviation("ASTRO-01", {"hr_mean_bpm": 72.0})
    assert dev["baseline_available"] is False
    assert dev["baseline_status"] == "not_available"
    assert "Missing historical data" in dev["message"]
    assert dev["provenance"]["observation_period_days"] == 0

def test_02_baseline_status_insufficient_data():
    """Verify INSUFFICIENT_DATA status when history is incomplete."""
    svc = PersonalBaselineInterface(default_status=BaselineStatus.INSUFFICIENT_DATA)
    assert svc.is_baseline_available("ASTRO-01") is False

    dev = svc.evaluate_deviation("ASTRO-01", {"hr_mean_bpm": 72.0})
    assert dev["baseline_available"] is False
    assert dev["baseline_status"] == "insufficient_data"
    assert "Insufficient longitudinal history" in dev["message"]

def test_03_baseline_status_invalid():
    """Verify INVALID status when calibration or telemetry artifacts compromise history."""
    svc = PersonalBaselineInterface(default_status=BaselineStatus.INVALID)
    assert svc.is_baseline_available("ASTRO-01") is False

    dev = svc.evaluate_deviation("ASTRO-01", {"hr_mean_bpm": 72.0})
    assert dev["baseline_available"] is False
    assert dev["baseline_status"] == "invalid"
    assert "Historical baseline data marked invalid" in dev["message"]

def test_04_baseline_status_available():
    """Verify AVAILABLE status activates personal profile comparison."""
    svc = PersonalBaselineInterface(default_status=BaselineStatus.AVAILABLE)
    assert svc.is_baseline_available("ASTRO-01") is True

    dev = svc.evaluate_deviation("ASTRO-01", {"hr_mean_bpm": 72.0})
    assert dev["baseline_available"] is True
    assert dev["baseline_status"] == "available"
    assert "Personal baseline available" in dev["message"]
    assert dev["provenance"]["observation_period_days"] == 30

def test_05_single_session_cannot_become_baseline():
    """Verify an isolated session is strictly rejected as a validated personal baseline."""
    svc = PersonalBaselineInterface()
    result = svc.validate_session_as_baseline({"hr_mean_bpm": 72.0, "hrv_rmssd_ms": 45.0})
    assert result["is_valid_baseline"] is False
    assert "isolated monitoring session cannot automatically become an established personal baseline" in result["reason"]

def test_06_set_baseline_status_dynamically():
    """Verify explicit dynamic update of baseline status."""
    svc = PersonalBaselineInterface()
    assert svc.is_baseline_available("ASTRO-01") is False
    svc.set_baseline_status(BaselineStatus.AVAILABLE)
    assert svc.is_baseline_available("ASTRO-01") is True
    svc.set_baseline_status(BaselineStatus.INVALID)
    assert svc.is_baseline_available("ASTRO-01") is False
