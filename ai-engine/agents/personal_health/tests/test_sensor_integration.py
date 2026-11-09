"""Unit tests for Sensor Quality Agent ingestion, stream validation, and quarantine rules."""
import pytest
import numpy as np
from personal_health.services.sensor_integration_service import (
    SensorIntegrationService,
    ValidatedSensorStream
)

def test_sensor_stream_immutability():
    """Verify that validated sensor data views are strictly read-only."""
    arr = np.array([1.0, 2.0, 3.0])
    ts = np.array([0.0, 0.5, 1.0])
    stream = ValidatedSensorStream(
        sensor_name="ECG",
        data=arr,
        timestamps=ts,
        sampling_rate=2.0,
        unit="mV",
        quality_score=0.99,
        status="VALID",
        warnings=[]
    )
    with pytest.raises(ValueError):
        stream.data[0] = 999.0
    with pytest.raises(ValueError):
        stream.timestamps[0] = 999.0

def test_sensor_quarantine_rejection():
    """Quarantine sensors that have critical failure, invalid status, or score below 0.60."""
    svc = SensorIntegrationService()
    mock_report = {
        "astronaut_id": "AST-TEST",
        "session_id": "SES-TEST",
        "overall_quality": {"score": 0.85, "status": "VALID"},
        "processing_decision": {"can_proceed": True, "rejected_sensors": ["EMG"], "warnings": []},
        "sensors": {
            "ECG": {"quality_score": 0.95, "status": "VALID", "recommendation": "ACCEPT", "critical_failure": False},
            "EMG": {"quality_score": 0.40, "status": "INVALID", "recommendation": "REJECT", "critical_failure": True}
        }
    }
    context, streams = svc.ingest_session(report_data=mock_report)
    assert "ECG" in context.valid_sensors
    assert len(context.quarantined_sensors) == 1
    assert context.quarantined_sensors[0].sensor == "EMG"
    assert "EMG" not in streams

def test_sensor_warnings_preserved():
    """Ensure that downstream warnings are properly captured and preserved."""
    svc = SensorIntegrationService()
    mock_report = {
        "astronaut_id": "AST-TEST",
        "session_id": "SES-TEST",
        "overall_quality": {"score": 0.88, "status": "ACCEPTABLE_WITH_WARNING"},
        "processing_decision": {"can_proceed": True, "rejected_sensors": [], "warnings": ["Moderate motion artifacts"]},
        "sensors": {
            "EDA": {
                "quality_score": 0.82,
                "status": "ACCEPTABLE_WITH_WARNING",
                "recommendation": "ACCEPT",
                "critical_failure": False,
                "issues": [{"reason_code": "MOTION_ARTIFACT", "explanation": "Transient spike detected"}]
            }
        }
    }
    context, _ = svc.ingest_session(report_data=mock_report)
    assert "EDA" in context.degraded_sensors
    assert "Moderate motion artifacts" in context.upstream_warnings
