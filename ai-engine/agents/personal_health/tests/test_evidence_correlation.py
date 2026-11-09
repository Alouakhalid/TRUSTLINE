"""Unit tests for deterministic evidence correlation and conflict identification."""
import pytest
from datetime import datetime
from personal_health.services.evidence_correlation_service import EvidenceCorrelationEngine
from personal_health.schemas.physiological_features import ExtractedFeature, PhysiologicalFeatureReport
from personal_health.schemas.ml_prediction import MLInferenceResult
from personal_health.schemas.symptom_event import SymptomEvent, InputChannel, SymptomCategory, SymptomSeverity
from personal_health.schemas.assessment import BaselineStatus

def test_evidence_correlation_motion_conflict():
    """Verify detection of discordance when acute stress alert occurs during high physical motion."""
    engine = EvidenceCorrelationEngine()

    acc_feat = ExtractedFeature(
        feature_name="acc_magnitude_mean",
        value=1.45,
        unit="g",
        sensor_source="ACC",
        time_window_seconds=60.0,
        extraction_method="mean_norm",
        quality_status="VALID",
        validity_status="VALID"
    )
    feature_report = PhysiologicalFeatureReport(
        astronaut_id="AST-001",
        session_id="SES-001",
        window_duration_seconds=60.0,
        all_features=[acc_feat],
        has_valid_core14=False
    )
    ml_res = MLInferenceResult(
        model_id="HGB-WESAD",
        model_name="HGB",
        version="1.0",
        target_definition="acute_stress",
        stress_probability=0.88,
        verdict="STRESS_ALERT"
    )

    explanations, conflicts, uncertainties, _, _ = engine.correlate_evidence(
        sensor_context=None,
        feature_report=feature_report,
        ml_result=ml_res,
        symptoms=[],
        health_profile=None,
        mission_context=None,
        retrieved_evidence=[],
        baseline_status=BaselineStatus.NOT_AVAILABLE
    )
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "ACTIVITY_TELEMETRY_DISCORDANCE"
    assert "physical exercise" in conflicts[0].clinical_resolution

def test_missing_baseline_uncertainty():
    """Verify deferred baseline status is transparently documented in uncertainties."""
    engine = EvidenceCorrelationEngine()
    _, _, uncertainties, _, _ = engine.correlate_evidence(
        sensor_context=None,
        feature_report=None,
        ml_result=None,
        symptoms=[],
        health_profile=None,
        mission_context=None,
        retrieved_evidence=[],
        baseline_status=BaselineStatus.NOT_AVAILABLE
    )
    assert any("baseline" in u.lower() for u in uncertainties)
