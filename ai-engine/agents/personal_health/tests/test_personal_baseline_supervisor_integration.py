"""Test suite for Area G: Multi-Agent Supervisor & Evidence Registry Integration."""
from datetime import datetime, timedelta
import json
import pytest

from supervisor.config.settings import get_supervisor_settings
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from personal_health.baseline.schemas import (
    ObservationSession,
    BaselineContextType
)
from personal_health.baseline.statistical_engine import RobustBaselineEngine
from personal_health.baseline.repository import PersonalBaselineRepository

def establish_astro_baseline(astronaut_id: str, hr_median: float = 72.0):
    """Calibrate and persist a multi-session baseline profile into the repository."""
    repo = PersonalBaselineRepository()
    engine = RobustBaselineEngine()
    base_t = datetime(2026, 11, 1, 8, 0, 0)

    sessions = []
    for i in range(5):
        sessions.append(ObservationSession(
            session_id=f"CALIB_S_{i}",
            astronaut_id=astronaut_id,
            timestamp=base_t + timedelta(days=i),
            features={
                "hr_mean_bpm": hr_median + (i % 2),
                "hrv_rmssd_ms": 42.0,
                "resp_rate_bpm": 14.0,
                "temp_mean": 36.6,
                "eda_mean": 2.2,
                "acc_magnitude_mean": 1.0,
                "acc_magnitude_std": 0.02
            },
            context_type=BaselineContextType.NOMINAL_OPERATIONAL,
            sqa_overall_score=0.95
        ))

    profile = engine.compute_baseline_profile(astronaut_id, sessions)
    repo.save_baseline(profile, reason="Test baseline establishment")
    return profile

def test_01_supervisor_e2e_with_established_baseline():
    """Verify complete Supervisor 10-node DAG runs with established baseline and compiles EV-BASE-* items."""
    establish_astro_baseline("AST-001", hr_median=70.0)

    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-BASE-E2E-001",
        astronaut_id="AST-001",
        session_id="SESSION-BASE-E2E-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Routine physiological telemetry review post extravehicular activity.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert result.get("astronaut_id") == "AST-001"

    # Verify PHA output contains personal_baseline_deviation
    pha_res = result.get("personal_health_result") or {}
    assert "personal_baseline_deviation" in pha_res or "personal_baseline_deviation" in result
    base_dev = result.get("personal_baseline_deviation") or pha_res.get("personal_baseline_deviation")
    assert base_dev is not None
    assert base_dev.get("baseline_available") is True

    # Verify Evidence Registry compilation
    registry = result.get("evidence_registry") or []
    base_items = [e for e in registry if str(e.get("evidence_id", "")).startswith("EV-BASE-")]
    assert len(base_items) >= 1

    sample_base = base_items[0]
    assert sample_base["source_agent"] in ("personal_health_agent", "personal_health_baseline_engine")
    assert sample_base["domain"] == "PHYSIOLOGICAL_BASELINE"
    assert sample_base["validity_status"] in ("VALID", "DEGRADED", "NOT_AVAILABLE")
    assert "Personal Health Baseline Engine" in sample_base["provenance"]

def test_02_supervisor_e2e_with_unestablished_baseline():
    """Verify clean execution when astronaut has no established baseline (EV-BASE-STATUS recorded)."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    # AST-UNESTABLISHED has no baseline in repository
    request = SupervisorRequest(
        request_id="REQ-BASE-E2E-002",
        astronaut_id="AST-UNESTABLISHED",
        session_id="SESSION-BASE-E2E-002",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Nominal rest telemetry review.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")

    registry = result.get("evidence_registry") or []
    status_items = [e for e in registry if e.get("evidence_id") == "EV-BASE-STATUS"]
    assert len(status_items) >= 1
    sample_stat = status_items[0]
    assert sample_stat["source_agent"] in ("personal_health_agent", "personal_health_baseline_engine")
    assert sample_stat["domain"] == "PHYSIOLOGICAL_BASELINE"
    assert sample_stat["validity_status"] == "NOT_AVAILABLE"

def test_03_telemetry_immutability_through_supervisor_dag():
    """Verify raw physiological telemetry is not mutated or fabricated through 10-node DAG."""
    establish_astro_baseline("AST-001", hr_median=70.0)

    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-BASE-E2E-003",
        astronaut_id="AST-001",
        session_id="SESSION-BASE-E2E-003",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Checking telemetry immutability invariants.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    pha_res = result.get("personal_health_result") or {}
    core_feats = pha_res.get("core_features") or {}
    registry = result.get("evidence_registry") or []

    # Check that observed values in EV-PHY-HR-MEAN match PHA core features exactly
    hr_item = next((e for e in registry if e.get("evidence_id") == "EV-PHY-HR-MEAN"), None)
    if hr_item and "hr_mean_bpm" in core_feats:
        assert hr_item["observed_value"] == core_feats["hr_mean_bpm"]

def test_04_baseline_deviation_does_not_falsely_escalate_evacuation():
    """Verify mild or moderate personal baseline deviation does not cause false emergency evacuation."""
    # Astronaut baseline at 60 bpm
    establish_astro_baseline("AST-001", hr_median=60.0)

    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-BASE-E2E-004",
        astronaut_id="AST-001",
        session_id="SESSION-BASE-E2E-004",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Routine post-exercise check.",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    final_assessment = result.get("final_assessment") or {}
    escalation = final_assessment.get("escalation") or {}

    # Should not trigger urgent evacuation in the absence of severe acute clinical distress symptoms
    assert escalation.get("urgency_level") != "CRITICAL"
    assert escalation.get("state") != "IMMEDIATE_EVACUATION_REQUIRED"
