"""Unit tests auditing Personal Health Agent integration, ML scope boundaries, and baseline status."""
import pytest
from datetime import datetime
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.schemas.evidence import RiskDomain, EvidenceSourceType
from risk_assessment.schemas.risk_rules import RiskLevel
from risk_assessment.services.evidence_normalization_service import EvidenceNormalizationService
from risk_assessment.agent.agent import RiskAssessmentAgent
from personal_health.schemas.assessment import (
    PersonalHealthAssessment,
    AssessmentStatus,
    BaselineStatus
)
from personal_health.schemas.physiological_features import (
    Core14Features,
    HRVDiagnosticReport,
    HRVStatus
)
from personal_health.schemas.ml_prediction import MLInferenceResult
from personal_health.schemas.symptom_event import SymptomEvent, SymptomSeverity, SymptomCategory
from personal_health.schemas.medical_document import ConfirmedMedicalFinding

def test_01_wesad_scope_separation():
    """Verify WESAD classifier probability is strictly isolated from medical risk probability."""
    pha = PersonalHealthAssessment(
        assessment_id="PHA-WESAD-01",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        core_features=Core14Features(
            hr_mean_bpm=72.0,
            hr_std_bpm=2.0,
            hrv_rmssd_ms=35.0,
            hrv_sdnn_ms=40.0,
            eda_mean=4.5,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        ),
        ml_findings=[
            MLInferenceResult(
                model_id="M-HGB-01",
                model_name="best_hist_gradient_boosting.pkl",
                version="1.0",
                target_definition="experimental_acute_stress",
                stress_probability=0.88,
                verdict="STRESS_ALERT"
            )
        ]
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        personal_health_assessment=pha
    )
    evidence = EvidenceNormalizationService.normalize_all(payload)
    ml_ev = next((e for e in evidence if "WESAD" in e.evidence_id), None)
    assert ml_ev is not None
    assert ml_ev.source_type == EvidenceSourceType.EXPERIMENTAL_ML_CLASSIFIER
    assert "experimental laboratory stress benchmark" in ml_ev.evidence_description.lower()

    agent = RiskAssessmentAgent()
    output = agent.assess(payload)
    assert output.overall_risk != RiskLevel.CRITICAL
    assert output.overall_risk != RiskLevel.HIGH

def test_02_zero_rmssd_artifact_handling():
    """Verify RMSSD = 0.0 ms with ZERO_VARIABILITY status is treated as an artifact, not an emergency."""
    pha = PersonalHealthAssessment(
        assessment_id="PHA-RMSSD-02",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        core_features=Core14Features(
            hr_mean_bpm=72.0,
            hr_std_bpm=0.0,
            hrv_rmssd_ms=0.0,
            hrv_sdnn_ms=0.0,
            eda_mean=4.69,
            eda_std=0.1,
            eda_iqr=0.2,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        ),
        hrv_diagnostics=HRVDiagnosticReport(
            ecg_sampling_rate=700.0,
            ecg_duration_seconds=60.0,
            total_r_peaks_detected=73,
            valid_r_peaks=73,
            total_rr_intervals=72,
            valid_nn_intervals=72,
            invalid_interval_count=0,
            mean_rr_ms=832.9,
            rmssd_ms=0.0,
            hrv_status=HRVStatus.ZERO_VARIABILITY,
            processing_warnings=["Constant RR intervals and zero variability observed."]
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        personal_health_assessment=pha
    )
    agent = RiskAssessmentAgent()
    output = agent.assess(payload)
    assert output.overall_risk != RiskLevel.CRITICAL
    assert output.escalation.required is False

def test_03_baseline_not_available_scope():
    """Verify baseline status NOT_AVAILABLE does not trigger ungrounded deviation warnings."""
    pha = PersonalHealthAssessment(
        assessment_id="PHA-BASE-03",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        assessment_status=AssessmentStatus.COMPLETED,
        baseline_status=BaselineStatus.NOT_AVAILABLE,
        core_features=Core14Features(
            hr_mean_bpm=72.0,
            hr_std_bpm=2.0,
            hrv_rmssd_ms=35.0,
            hrv_sdnn_ms=40.0,
            eda_mean=4.5,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.0,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.02,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        )
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        personal_health_assessment=pha
    )
    agent = RiskAssessmentAgent()
    output = agent.assess(payload)
    assert not any("deviation from personal baseline" in str(u).lower() for u in output.uncertainties)

def test_04_confirmed_medical_records_ingestion():
    """Verify confirmed laboratory findings are included in evidence summary."""
    rec = ConfirmedMedicalFinding(
        record_id="REC-LAB-01",
        document_id="DOC-99",
        astronaut_id="AST-001",
        test_name="Potassium",
        value_string="4.2",
        numeric_value=4.2,
        unit="mEq/L",
        reference_range="3.5-5.0",
        confirmed_by="DR-REVIEWER"
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        confirmed_medical_records=[rec]
    )
    evidence = EvidenceNormalizationService.normalize_all(payload)
    pot_ev = next((e for e in evidence if "potassium" in e.metric_name), None)
    assert pot_ev is not None
    assert pot_ev.is_confirmed is True
    assert pot_ev.observed_value == 4.2
