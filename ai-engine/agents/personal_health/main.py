"""Main CLI entrypoint and orchestrator for TRUSTLINE Personal Health Agent."""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

if __package__ is None or __package__ == "":
    cur = Path(__file__).resolve().parent
    while cur != cur.parent:
        if (cur / "ai-engine").exists() or (cur / "personal_health").exists():
            if str(cur) not in sys.path:
                sys.path.insert(0, str(cur))
            break
        cur = cur.parent

from personal_health.config.settings import get_settings
from personal_health.services.health_profile_service import HealthProfileService
from personal_health.services.sensor_integration_service import SensorIntegrationService
from personal_health.services.feature_extraction_service import FeatureExtractionService
from personal_health.services.ml_inference_service import MLInferenceService
from personal_health.services.symptom_service import SymptomService
from personal_health.services.groq_voice_service import GroqVoiceService
from personal_health.services.baseline_interface import PersonalBaselineInterface
from personal_health.services.mission_context_service import MissionContextService
from personal_health.services.rag_service import MedicalRAGService
from personal_health.services.escalation_service import EmergencyEscalationService
from personal_health.services.evidence_correlation_service import EvidenceCorrelationEngine
from personal_health.agent.agent import generate_clinical_synthesis, run_personal_health_crew
from personal_health.schemas.assessment import (
    PersonalHealthAssessment,
    AssessmentStatus,
    BaselineStatus,
    EscalationDetails
)
from personal_health.schemas.symptom_event import SymptomAssessmentStatus

def run_personal_health_pipeline(
    manifest_path: str,
    quality_report_path: str,
    symptom_text: Optional[str] = None,
    symptom_voice_path: Optional[str] = None,
    voice_language: Optional[str] = None,
    run_crew: bool = False,
    output_dir: str = ""
) -> int:
    """Execute end-to-end Personal Health assessment pipeline."""
    cfg = get_settings()

    q_file = Path(quality_report_path).resolve()
    if not q_file.exists():
        candidate = cfg.sensor_quality_dir / "data" / "output" / "sensor_quality_report.json"
        if candidate.exists():
            q_file = candidate

    if not q_file.exists():
        sys.stderr.write(f"Sensor Quality Report file not found: {q_file}\n")
        return 1

    m_file = Path(manifest_path).resolve()
    manifest_data = None
    if m_file.exists():
        try:
            with open(m_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as exc:
            sys.stderr.write(f"Warning: could not read manifest: {str(exc)}\n")

    sensor_service = SensorIntegrationService(base_data_dir=cfg.sensor_quality_dir / "data")
    try:
        sensor_context, valid_streams = sensor_service.ingest_session(
            report_data=q_file,
            manifest_data=manifest_data
        )
    except Exception as exc:
        sys.stderr.write(f"Failed to ingest sensor quality output: {str(exc)}\n")
        return 1

    astronaut_id = sensor_context.astronaut_id
    session_id = sensor_context.session_id

    symptom_service = SymptomService()
    reported_symptoms = []
    clarification_requests = []

    if symptom_voice_path:
        try:
            v_event, v_clar, v_res = symptom_service.process_voice_symptom(
                audio_file_path=symptom_voice_path,
                astronaut_id=astronaut_id,
                session_id=session_id,
                language=voice_language
            )
            if v_event:
                reported_symptoms.append(v_event)
            if v_clar:
                clarification_requests.append(v_clar)
        except Exception as exc:
            sys.stderr.write(f"Voice symptom ingestion error: {str(exc)}\n")

    if symptom_text:
        try:
            t_event, t_clar = symptom_service.process_text_symptom(
                text=symptom_text,
                astronaut_id=astronaut_id,
                session_id=session_id
            )
            if t_event:
                reported_symptoms.append(t_event)
            if t_clar:
                clarification_requests.append(t_clar)
        except Exception as exc:
            sys.stderr.write(f"Text symptom ingestion error: {str(exc)}\n")

    escalation_service = EmergencyEscalationService()
    escalation = escalation_service.evaluate_immediate_escalation(
        symptoms=reported_symptoms,
        telemetry_features=None,
        critical_sensors_available="ECG" in valid_streams,
        sensor_quality_valid=sensor_context.can_proceed
    )

    profile_service = HealthProfileService()
    health_profile = profile_service.get_or_create_profile(astronaut_id)

    mission_service = MissionContextService()
    mission_ctx = mission_service.get_mission_context(session_id)

    baseline_service = PersonalBaselineInterface()
    baseline_stat = baseline_service.get_baseline_status(astronaut_id)

    feature_service = FeatureExtractionService()
    feature_report = feature_service.extract_features(
        streams=valid_streams,
        astronaut_id=astronaut_id,
        session_id=session_id
    )

    if not escalation.required and feature_report.core_features:
        feat_dict = feature_report.core_features.to_feature_dict()
        escalation = escalation_service.evaluate_immediate_escalation(
            symptoms=reported_symptoms,
            telemetry_features=feat_dict,
            critical_sensors_available="ECG" in valid_streams,
            sensor_quality_valid=sensor_context.can_proceed
        )

    ml_service = MLInferenceService()
    ml_findings = []
    if feature_report.core_features:
        try:
            pred = ml_service.predict_stress(feature_report.core_features)
            ml_findings.append(pred)
        except Exception as exc:
            sys.stderr.write(f"ML inference error: {str(exc)}\n")

    rag_service = MedicalRAGService()
    query_str = "stress physiology microgravity protocol"
    if reported_symptoms:
        query_str = f"{reported_symptoms[0].symptom_type} {query_str}"
    retrieved_evidence = rag_service.query_medical_evidence(query=query_str, top_k=2)

    correlation_engine = EvidenceCorrelationEngine()
    primary_ml = ml_findings[0] if ml_findings else None
    explanations, conflicts, uncertainties, missing_info, follow_up = correlation_engine.correlate_evidence(
        sensor_context=sensor_context,
        feature_report=feature_report,
        ml_result=primary_ml,
        symptoms=reported_symptoms,
        health_profile=health_profile,
        mission_context=mission_ctx,
        retrieved_evidence=retrieved_evidence,
        baseline_status=baseline_stat
    )

    assessment_status = AssessmentStatus.COMPLETED
    if escalation.required:
        assessment_status = AssessmentStatus.URGENT_ESCALATION
    elif clarification_requests:
        assessment_status = AssessmentStatus.REQUIRES_CLARIFICATION
    elif not sensor_context.can_proceed:
        assessment_status = AssessmentStatus.INSUFFICIENT_EVIDENCE

    briefing_context = (
        f"Astronaut: {astronaut_id} | Session: {session_id}\n"
        f"Overall Quality: {sensor_context.overall_quality_score:.3f} ({sensor_context.overall_quality_status})\n"
        f"Core Features Extracted: {feature_report.has_valid_core14}\n"
        f"ML Stress Verdict: {primary_ml.verdict if primary_ml else 'N/A'} (Prob={primary_ml.stress_probability if primary_ml else 0.0})\n"
        f"Reported Symptoms Count: {len(reported_symptoms)}\n"
        f"Escalation Required: {escalation.required} ({escalation.urgency_level}) [Status: {escalation.status.value}]\n"
        f"Evidence Conflicts: {len(conflicts)}\n"
        f"Key Explanations: {'; '.join(explanations)}"
    )

    symptom_status = SymptomAssessmentStatus.NO_SYMPTOMS_REPORTED
    if not reported_symptoms and symptom_text is None and symptom_voice_path is None:
        symptom_status = SymptomAssessmentStatus.NO_SYMPTOMS_REPORTED

    rmssd_val = feature_report.core_features.hrv_rmssd_ms if feature_report.core_features else 0.0
    hrv_stat = feature_report.hrv_diagnostics.hrv_status.value if feature_report.hrv_diagnostics else "ZERO_VARIABILITY"
    ground_truth = {
        "astronaut_id": astronaut_id,
        "session_id": session_id,
        "hr_value": feature_report.core_features.hr_mean_bpm if feature_report.core_features else 0.0,
        "rmssd_value": rmssd_val,
        "rmssd_status": "insufficient_variance" if rmssd_val < 1.0 else "available",
        "hrv_status": hrv_stat,
        "escalation_status": escalation.status.value,
        "eda_value": feature_report.core_features.eda_mean if feature_report.core_features else 0.0,
        "hgb_prob": primary_ml.stress_probability if primary_ml else 0.0,
        "hgb_verdict": primary_ml.verdict if primary_ml else "N/A",
        "mission_day": mission_ctx.microgravity_exposure_days if mission_ctx.is_context_supplied else None,
        "has_clinical_fluid_shift_evidence": False,
        "symptom_count": len(reported_symptoms),
        "symptom_confirmed_negative": False,
        "baseline_status": baseline_stat.value,
        "has_resp_measurement": "RESP" in valid_streams,
        "has_acc_measurement": "ACC" in valid_streams,
    }

    llm_synthesis = None
    if run_crew:
        try:
            llm_synthesis = run_personal_health_crew(
                astronaut_id=astronaut_id,
                session_id=session_id,
                context_str=briefing_context
            )
        except Exception:
            llm_synthesis = generate_clinical_synthesis(
                astronaut_id=astronaut_id,
                session_id=session_id,
                evidence_summary=briefing_context,
                ground_truth=ground_truth
            )
    else:
        llm_synthesis = generate_clinical_synthesis(
            astronaut_id=astronaut_id,
            session_id=session_id,
            evidence_summary=briefing_context,
            ground_truth=ground_truth
        )

    assessment = PersonalHealthAssessment(
        assessment_id=f"PHA-{uuid.uuid4().hex[:8].upper()}",
        astronaut_id=astronaut_id,
        session_id=session_id,
        execution_timestamp=datetime.utcnow(),
        assessment_status=assessment_status,
        baseline_status=baseline_stat,
        sensor_quality_summary=sensor_context,
        core_features=feature_report.core_features,
        physiological_findings=feature_report.all_features,
        hrv_diagnostics=feature_report.hrv_diagnostics,
        ml_findings=ml_findings,
        symptom_findings=reported_symptoms,
        symptom_assessment_status=symptom_status,
        health_profile_summary={
            "age": health_profile.basic_info.age,
            "bmi": health_profile.basic_info.bmi,
            "resting_hr": health_profile.physical_fitness.resting_heart_rate_bpm,
            "known_constraints": health_profile.medical_history.medical_constraints
        },
        mission_context=mission_ctx,
        retrieved_evidence=retrieved_evidence,
        possible_explanations=explanations,
        evidence_conflicts=conflicts,
        uncertainties=uncertainties,
        missing_information=missing_info,
        recommended_follow_up=follow_up,
        clarification_requests=clarification_requests,
        escalation=escalation,
        next_agent="risk_assessment_agent",
        llm_executive_synthesis=llm_synthesis
    )

    target_dir = Path(output_dir).resolve() if output_dir else cfg.output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "personal_health_assessment.json"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(assessment.model_dump_json(indent=2))

    sys.stdout.write("=====================================================\n")
    sys.stdout.write("TRUSTLINE PERSONAL HEALTH ASSESSMENT REPORT\n")
    sys.stdout.write("=====================================================\n")
    sys.stdout.write(f"Assessment ID: {assessment.assessment_id}\n")
    sys.stdout.write(f"Astronaut: {assessment.astronaut_id} | Session: {assessment.session_id}\n")
    sys.stdout.write(f"Status: {assessment.assessment_status.value}\n")
    sys.stdout.write(f"Baseline Status: {assessment.baseline_status.value}\n")
    sys.stdout.write(f"Emergency Escalation: {assessment.escalation.status.value} | Required={assessment.escalation.required} ({assessment.escalation.urgency_level})\n")
    if assessment.escalation.triggers:
        sys.stdout.write(f"  Triggers: {assessment.escalation.triggers}\n")
    if assessment.escalation.data_gaps:
        sys.stdout.write(f"  Data Gaps: {assessment.escalation.data_gaps}\n")
    if assessment.escalation.uncertainty_notes:
        sys.stdout.write(f"  Uncertainty Notes: {assessment.escalation.uncertainty_notes}\n")
    if assessment.core_features:
        sys.stdout.write(f"Physiology: HR={assessment.core_features.hr_mean_bpm:.1f} bpm | RMSSD={assessment.core_features.hrv_rmssd_ms:.1f} ms | EDA={assessment.core_features.eda_mean:.2f} uS\n")
    if assessment.hrv_diagnostics:
        sys.stdout.write(f"HRV Diagnostics: Status={assessment.hrv_diagnostics.hrv_status.value} | R-peaks={assessment.hrv_diagnostics.r_peaks_detected} | Valid RR={assessment.hrv_diagnostics.valid_rr_intervals_count} | Mean RR={assessment.hrv_diagnostics.mean_rr_ms:.1f} ms | Artifacts={assessment.hrv_diagnostics.artifact_count}\n")
        sys.stdout.write(f"HRV Diagnostic Note: {assessment.hrv_diagnostics.diagnostic_note}\n")
    if assessment.ml_findings:
        sys.stdout.write(f"ML Classifier (HGB): Stress Prob={assessment.ml_findings[0].stress_probability:.4f} | Verdict={assessment.ml_findings[0].verdict}\n")
    sys.stdout.write(f"Symptom Assessment: {assessment.symptom_assessment_status.value}\n")
    if assessment.symptom_findings:
        sys.stdout.write(f"Symptoms ({len(assessment.symptom_findings)}): {[s.symptom_type for s in assessment.symptom_findings]}\n")
    if assessment.evidence_conflicts:
        sys.stdout.write(f"Evidence Conflicts: {[c.conflict_type for c in assessment.evidence_conflicts]}\n")
    if assessment.llm_executive_synthesis:
        sys.stdout.write("-----------------------------------------------------\n")
        sys.stdout.write("EXECUTIVE CLINICAL SYNTHESIS (GROQ LLM):\n")
        sys.stdout.write(f"{assessment.llm_executive_synthesis}\n")
    sys.stdout.write(f"Report JSON written to: {out_file}\n")
    sys.stdout.write("=====================================================\n")

    return 0

def main():
    parser = argparse.ArgumentParser(description="TRUSTLINE Personal Health Agent CLI")
    parser.add_argument("--manifest", type=str, default="../sensor_quality/data/input/astronaut_health_data.json", help="Path to manifest JSON")
    parser.add_argument("--quality-report", type=str, default="../sensor_quality/data/output/sensor_quality_report.json", help="Path to sensor quality report JSON")
    parser.add_argument("--symptom-text", type=str, default=None, help="Subjective symptom text statement")
    parser.add_argument("--symptom-voice", type=str, default=None, help="Audio file path to transcribe via Groq Whisper")
    parser.add_argument("--voice-lang", type=str, default=None, help="Audio language code (e.g. en, ar)")
    parser.add_argument("--run-crew", action="store_true", help="Execute CrewAI agent")
    parser.add_argument("--output", type=str, default="", help="Output directory")

    args = parser.parse_args()
    return run_personal_health_pipeline(
        manifest_path=args.manifest,
        quality_report_path=args.quality_report,
        symptom_text=args.symptom_text,
        symptom_voice_path=args.symptom_voice,
        voice_language=args.voice_lang,
        run_crew=args.run_crew,
        output_dir=args.output
    )

if __name__ == "__main__":
    sys.exit(main())
