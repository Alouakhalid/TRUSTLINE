"""Deterministic multi-source evidence correlation and clinical synthesis engine."""
from typing import Dict, List, Optional, Tuple, Any

from ..schemas.sensor_input import SensorIngestionContext
from ..schemas.physiological_features import PhysiologicalFeatureReport, ExtractedFeature
from ..schemas.ml_prediction import MLInferenceResult
from ..schemas.symptom_event import SymptomEvent
from ..schemas.health_profile import AstronautHealthProfile
from ..schemas.mission_context import MissionContext
from ..schemas.rag_evidence import RAGEvidenceItem
from ..schemas.assessment import (
    BaselineStatus,
    EvidenceConflict
)

class EvidenceCorrelationEngine:
    """Deterministic evidence synthesis preserving provenance and identifying conflicts."""

    def correlate_evidence(
        self,
        sensor_context: Optional[SensorIngestionContext],
        feature_report: Optional[PhysiologicalFeatureReport],
        ml_result: Optional[MLInferenceResult],
        symptoms: List[SymptomEvent],
        health_profile: Optional[AstronautHealthProfile],
        mission_context: Optional[MissionContext],
        retrieved_evidence: List[RAGEvidenceItem],
        baseline_status: BaselineStatus = BaselineStatus.NOT_AVAILABLE
    ) -> Tuple[List[str], List[EvidenceConflict], List[str], List[str], List[str]]:
        """Synthesize all available modalities into structured clinical explanations."""
        possible_explanations: List[str] = []
        conflicts: List[EvidenceConflict] = []
        uncertainties: List[str] = []
        missing_information: List[str] = []
        recommended_follow_up: List[str] = []

        feat_map: Dict[str, float] = {}
        if feature_report:
            feat_map = {f.feature_name: f.value for f in feature_report.all_features}

        if baseline_status != BaselineStatus.AVAILABLE:
            uncertainties.append("Individualized personal baseline is not yet established; population reference norms utilized.")

        if sensor_context:
            if sensor_context.quarantined_sensors:
                for q in sensor_context.quarantined_sensors:
                    uncertainties.append(f"Sensor {q.sensor} was quarantined ({q.rejection_reason}). Features unavailable.")
            if sensor_context.upstream_warnings:
                for w in sensor_context.upstream_warnings:
                    uncertainties.append(f"Upstream sensor quality warning: {w}")

        hr = feat_map.get("hr_mean_bpm")
        rmssd = feat_map.get("hrv_rmssd_ms")
        eda = feat_map.get("eda_mean")
        acc = feat_map.get("acc_magnitude_mean")
        resp = feat_map.get("resp_rate_bpm")

        is_high_motion = acc is not None and acc > 1.05
        is_stress_predicted = ml_result is not None and ml_result.verdict == "STRESS_ALERT"

        if is_stress_predicted and is_high_motion:
            conflicts.append(EvidenceConflict(
                conflict_type="ACTIVITY_TELEMETRY_DISCORDANCE",
                modality_a="ML_STRESS_CLASSIFIER",
                finding_a="Acute stress alert triggered by elevated heart rate and electrodermal arousal",
                modality_b="INERTIAL_ACCELEROMETRY",
                finding_b=f"High physical movement intensity (acc_magnitude={acc:.2f}g)",
                clinical_resolution="Elevated autonomic tone is primarily attributable to physical exercise rather than isolated psychological distress."
            ))
            possible_explanations.append("Autonomic tachycardia driven by acute physical activity and biomechanical locomotion.")
        elif is_stress_predicted and not is_high_motion:
            possible_explanations.append("Sympathovagal autonomic shift consistent with acute cognitive or psychological stress state in the absence of significant physical locomotion.")
            recommended_follow_up.append("Initiate 15-minute tactical respiratory regulation (6 breaths/min resonant breathing).")

        reported_symptom_types = [s.symptom_type.lower() for s in symptoms]
        if "dyspnea" in reported_symptom_types or "shortness_of_breath" in reported_symptom_types:
            if resp is not None and 12.0 <= resp <= 18.0:
                conflicts.append(EvidenceConflict(
                    conflict_type="SUBJECTIVE_OBJECTIVE_VENTILATORY_DISPARITY",
                    modality_a="ASTRONAUT_SYMPTOM_REPORT",
                    finding_a="Self-reported difficulty breathing or shortness of breath",
                    modality_b="RESPIRATORY_SENSOR_TELEMETRY",
                    finding_b=f"Nominal resting breathing frequency ({resp:.1f} breaths/min)",
                    clinical_resolution="May indicate subjective anxiety hyper-vigilance or early microgravity cephalad fluid congestion rather than overt mechanical ventilatory failure."
                ))

        if rmssd is not None and rmssd < 1.0:
            uncertainties.append("HRV metric (RMSSD=0.0 ms) exhibits zero beat-to-beat interval variability (synthetic periodic signal or unvarying rhythm); invalid for vagal parasympathetic evaluation.")

        if ml_result is not None:
            possible_explanations.append(
                f"WESAD acute stress model prediction: {ml_result.verdict} (p={ml_result.stress_probability:.4f}). "
                f"Validated strictly as experimental acute stress classifier; does not evaluate general clinical health, pathology, or psychological stability."
            )

        if mission_context and mission_context.is_context_supplied and mission_context.microgravity_exposure_days is not None:
            possible_explanations.append(f"Supplied mission context: Microgravity exposure day {mission_context.microgravity_exposure_days:.1f}.")

        if mission_context and mission_context.is_context_supplied and mission_context.actual_sleep_hours and mission_context.actual_sleep_hours < 6.0:
            possible_explanations.append(f"Supplied sleep record: Restriced sleep duration ({mission_context.actual_sleep_hours:.1f}h).")

        if feature_report:
            for f in feature_report.all_features:
                if f.exploratory_ultra_short_term:
                    uncertainties.append(f"{f.feature_name} derived from short recording window (< 300s); classified as exploratory ultra-short-term measurement.")

        if not symptoms:
            missing_information.append(
                "Symptom status: NO_SYMPTOMS_REPORTED. No subjective symptom survey was submitted; "
                "absence of reported symptoms does not constitute a confirmed negative clinical assessment."
            )

        if baseline_status != BaselineStatus.AVAILABLE:
            uncertainties.append(
                "Personal baseline status: NOT_AVAILABLE. Individualized baseline comparison was not performed; "
                "current telemetry represents an unvalidated single-session observation and must not be registered as a confirmed personal baseline."
            )

        if not recommended_follow_up:
            recommended_follow_up.append("Maintain standard telemetry monitoring pending baseline establishment.")

        return possible_explanations, conflicts, uncertainties, missing_information, recommended_follow_up
