"""Immediate safety escalation service bypassing non-urgent pipeline latency."""
from typing import Dict, List, Optional, Tuple, Any
from ..schemas.symptom_event import SymptomEvent, SymptomSeverity
from ..schemas.assessment import EscalationDetails, EmergencyAssessmentStatus

RED_LINE_SYMPTOMS = {
    "chest_pain": ["chest pain", "crushing chest", "heart pain", "pressure in chest", "وجع في الصدر", "الم في الصدر"],
    "respiratory_distress": ["cannot breathe", "severe shortness of breath", "gasping", "ضيق تنفس شديد", "مش قادر اتنفس"],
    "loss_of_consciousness": ["blackout", "passed out", "syncope", "lost consciousness", "اغماء", "فقدان الوعي"],
    "acute_neurological": ["cannot speak", "facial drooping", "loss of vision", "hemiparesis", "شلل", "فقدان النطق"]
}

class EmergencyEscalationService:
    """Safety interface detecting immediate medical escalation conditions via deterministic state evaluation."""

    def evaluate_immediate_escalation(
        self,
        symptoms: List[SymptomEvent],
        telemetry_features: Optional[Dict[str, float]] = None,
        critical_sensors_available: bool = True,
        sensor_quality_valid: bool = True
    ) -> EscalationDetails:
        """Evaluate emergency red-lines with deterministic 4-state safety logic."""
        try:
            triggers: List[str] = []
            reason_codes: List[str] = []
            actions: List[str] = []

            for s in symptoms:
                text = f"{s.symptom_type} {s.description}".lower()

                for category, phrases in RED_LINE_SYMPTOMS.items():
                    if any(phrase in text for phrase in phrases):
                        triggers.append(f"Red-Line Symptom Detected: {s.symptom_type}")
                        reason_codes.append(f"EMERGENCY_{category.upper()}")

                if s.severity in (SymptomSeverity.SEVERE, SymptomSeverity.CRITICAL) and s.symptom_category.value == "CARDIORESPIRATORY":
                    triggers.append(f"Severe Cardiorespiratory Symptom: {s.symptom_type}")
                    if "EMERGENCY_CRITICAL_CARDIORESPIRATORY" not in reason_codes:
                        reason_codes.append("EMERGENCY_CRITICAL_CARDIORESPIRATORY")

            if telemetry_features:
                hr = telemetry_features.get("hr_mean_bpm")
                if hr is not None:
                    if hr > 160.0:
                        triggers.append(f"Telemetry Extreme Tachycardia at Rest: {hr:.1f} bpm")
                        reason_codes.append("EMERGENCY_EXTREME_TACHYCARDIA")
                    elif hr < 40.0:
                        triggers.append(f"Telemetry Extreme Bradycardia at Rest: {hr:.1f} bpm")
                        reason_codes.append("EMERGENCY_EXTREME_BRADYCARDIA")

            if reason_codes:
                actions = [
                    "Notify Flight Surgeon immediately via high-priority telemetry alert",
                    "Direct astronaut to cease physical tasks and assume seated/horizontal position",
                    "Deploy Crew Medical Restraint System (CMRS) and medical diagnostic kit"
                ]
                return EscalationDetails(
                    status=EmergencyAssessmentStatus.ESCALATION_REQUIRED,
                    required=True,
                    urgency_level="CRITICAL",
                    reason_codes=reason_codes,
                    triggers=triggers,
                    immediate_actions=actions,
                    protocol_reference="ISS-MEDOPS-REDLINE-2025-V4.2",
                    uncertainty_notes=[],
                    data_gaps=[]
                )

            data_gaps: List[str] = []
            uncertainty_notes: List[str] = []

            has_missing_telemetry = (
                telemetry_features is None or
                telemetry_features.get("hr_mean_bpm") is None
            )

            if has_missing_telemetry:
                data_gaps.append("Cardiac heart rate (hr_mean_bpm) telemetry unavailable or omitted")
            if not critical_sensors_available:
                data_gaps.append("Critical physiological sensors (ECG) unavailable or quarantined")
            if not sensor_quality_valid:
                data_gaps.append("Sensor quality gate indicates unvalidated or compromised signal telemetry")

            if data_gaps:
                uncertainty_notes.append(
                    "Emergency status cannot be conclusively confirmed as NOMINAL due to missing or unvalidated physiological telemetry; close monitoring maintained."
                )
                return EscalationDetails(
                    status=EmergencyAssessmentStatus.INSUFFICIENT_DATA,
                    required=False,
                    urgency_level="INDETERMINATE",
                    reason_codes=[],
                    triggers=[],
                    immediate_actions=[
                        "Maintain active telemetry acquisition",
                        "Request sensor re-validation from Sensor Quality Agent"
                    ],
                    protocol_reference="ISS-MEDOPS-TELEMETRY-GAPS-V2.1",
                    uncertainty_notes=uncertainty_notes,
                    data_gaps=data_gaps
                )

            return EscalationDetails(
                status=EmergencyAssessmentStatus.NO_TRIGGER_DETECTED,
                required=False,
                urgency_level="NO_EMERGENCY_TRIGGER",
                reason_codes=[],
                triggers=[],
                immediate_actions=[],
                uncertainty_notes=[
                    "NO_TRIGGER_DETECTED indicates only that no configured emergency escalation rule was triggered using the available valid evidence; this observation alone does not confirm that the astronaut is healthy or that no medical risk exists."
                ],
                data_gaps=[]
            )

        except Exception as exc:
            return EscalationDetails(
                status=EmergencyAssessmentStatus.ASSESSMENT_FAILED,
                required=False,
                urgency_level="SYSTEM_ERROR",
                reason_codes=["ERROR_EVALUATION_FAILURE"],
                triggers=[f"Exception during escalation evaluation: {str(exc)}"],
                immediate_actions=[
                    "Notify system operator of emergency escalation engine failure",
                    "Perform manual clinical telemetry review"
                ],
                protocol_reference="ISS-SAFETY-FALLBACK-V1.0",
                uncertainty_notes=[f"Evaluation failed with exception: {type(exc).__name__}: {str(exc)}"],
                data_gaps=["Escalation evaluation pipeline interrupted"]
            )
