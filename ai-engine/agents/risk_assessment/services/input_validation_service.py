"""Input validation service verifying schema compatibility and evidence provenance."""
from datetime import datetime
from typing import Dict, List, Tuple, Any
from ..schemas.risk_input import RiskAssessmentInput
from ..schemas.evidence import EvidenceValidity

class InputValidationError(Exception):
    """Raised when risk assessment input fails fundamental structural validation."""
    pass

class InputValidationService:
    """Validates upstream multi-agent reports, identifiers, and safety constraints."""

    @classmethod
    def validate_input(cls, payload: RiskAssessmentInput) -> Tuple[bool, List[str], List[str]]:
        """Validate input payload and return validation status, errors, and warnings."""
        errors: List[str] = []
        warnings: List[str] = []

        if not payload.astronaut_id or not payload.astronaut_id.strip():
            errors.append("Missing required astronaut_id.")

        if not payload.session_id or not payload.session_id.strip():
            errors.append("Missing required session_id.")

        if not payload.assessment_id or not payload.assessment_id.strip():
            errors.append("Missing required assessment_id.")

        if payload.sensor_quality_report is not None:
            sqr = payload.sensor_quality_report
            if sqr.astronaut_id != payload.astronaut_id:
                errors.append(
                    f"Astronaut ID mismatch in SensorQualityReport: expected '{payload.astronaut_id}', found '{sqr.astronaut_id}'."
                )
            if not sqr.sensors:
                warnings.append("SensorQualityReport contains an empty sensors mapping.")

        if payload.personal_health_assessment is not None:
            pha = payload.personal_health_assessment
            if pha.astronaut_id != payload.astronaut_id:
                errors.append(
                    f"Astronaut ID mismatch in PersonalHealthAssessment: expected '{payload.astronaut_id}', found '{pha.astronaut_id}'."
                )

        unconfirmed_records: List[str] = []
        for rec in payload.confirmed_medical_records:
            if not rec.test_name or rec.numeric_value is None and not rec.value_string:
                warnings.append(f"Incomplete medical record '{rec.record_id}' detected.")
            if "pending" in getattr(rec, "confirmation_status", "").lower():
                unconfirmed_records.append(rec.record_id)

        if unconfirmed_records:
            errors.append(
                f"Safety violation: Unconfirmed pending OCR records detected in confirmed records list ({unconfirmed_records})."
            )

        if payload.mission_context is not None:
            mc = payload.mission_context
            if mc.cabin_o2_percent is not None and (mc.cabin_o2_percent < 0.0 or mc.cabin_o2_percent > 100.0):
                errors.append(f"Invalid cabin oxygen percentage: {mc.cabin_o2_percent}%.")
            if mc.cabin_co2_percent is not None and (mc.cabin_co2_percent < 0.0 or mc.cabin_co2_percent > 10.0):
                errors.append(f"Invalid cabin CO2 percentage: {mc.cabin_co2_percent}%.")
            if mc.cabin_pressure_kpa is not None and mc.cabin_pressure_kpa <= 0.0:
                errors.append(f"Invalid cabin pressure: {mc.cabin_pressure_kpa} kPa.")

        is_valid = len(errors) == 0
        return is_valid, errors, warnings
