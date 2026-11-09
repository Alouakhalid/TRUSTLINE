"""Unit tests for Risk Assessment Agent input schema validation and safety rejection."""
import pytest
from datetime import datetime
from risk_assessment.schemas.risk_input import RiskAssessmentInput
from risk_assessment.services.input_validation_service import InputValidationService
from personal_health.schemas.medical_document import ConfirmedMedicalFinding
from personal_health.schemas.mission_context import MissionContext

def test_01_valid_payload():
    """Verify clean payload satisfies all structural and identity requirements."""
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001"
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is True
    assert len(errors) == 0

def test_02_missing_astronaut_id():
    """Verify empty astronaut identifier is rejected."""
    payload = RiskAssessmentInput(
        astronaut_id="",
        session_id="SESSION-001"
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is False
    assert any("astronaut_id" in err for err in errors)

def test_03_missing_session_id():
    """Verify empty session identifier is rejected."""
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id=""
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is False
    assert any("session_id" in err for err in errors)

def test_04_astronaut_id_mismatch_in_sqr():
    """Verify mismatch between top-level astronaut ID and SQR astronaut ID is flagged."""
    from sensor_quality.schemas.output_schema import SensorQualityReport, OverallQuality, ProcessingDecision
    from sensor_quality.schemas.signal_schema import QualityStatus

    sqr = SensorQualityReport(
        astronaut_id="AST-MISMATCH",
        session_id="SESSION-001",
        execution_timestamp=datetime.utcnow().isoformat(),
        overall_quality=OverallQuality(
            score=0.95,
            status=QualityStatus.VALID,
            valid_sensors_count=1,
            total_sensors_count=1
        ),
        sensors={},
        processing_decision=ProcessingDecision(can_proceed=True)
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        sensor_quality_report=sqr
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is False
    assert any("mismatch" in err.lower() for err in errors)

def test_05_rejection_of_pending_medical_records():
    """Verify unconfirmed pending medical records are strictly rejected from confirmed records list."""
    rec = ConfirmedMedicalFinding(
        record_id="REC-PENDING-01",
        document_id="DOC-01",
        astronaut_id="AST-001",
        test_name="Hemoglobin",
        value_string="14.5",
        numeric_value=14.5,
        unit="g/dL",
        confirmed_by="unconfirmed_pending_review"
    )
    rec.__dict__["confirmation_status"] = "PENDING_REVIEW"

    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        confirmed_medical_records=[rec]
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is False
    assert any("pending" in err.lower() for err in errors)

def test_06_mission_context_invalid_ranges():
    """Verify out-of-bounds atmospheric percentages trigger validation errors."""
    ctx = MissionContext.model_construct(
        cabin_o2_percent=120.0,
        cabin_co2_percent=-1.0,
        cabin_pressure_kpa=-10.0
    )
    payload = RiskAssessmentInput(
        astronaut_id="AST-001",
        session_id="SESSION-001",
        mission_context=ctx
    )
    is_valid, errors, warnings = InputValidationService.validate_input(payload)
    assert is_valid is False
    assert len(errors) >= 2
