"""Personal Health Agent adapter orchestrating feature extraction, ML inference, and clinical synthesis."""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple
from .base import BaseAgentAdapter
from ..schemas.assessment import AgentExecutionState, AgentExecutionStatus
from ..config.settings import get_supervisor_settings

class PersonalHealthAdapter(BaseAgentAdapter):
    """Adapter invoking Personal Health Agent pipeline and mapping outputs to state."""

    def __init__(self):
        super().__init__(agent_name="personal_health_agent")

    def run(self, state: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentExecutionStatus]:
        cfg = get_supervisor_settings()
        astronaut_id = state.get("astronaut_id", "AST-UNKNOWN")
        session_id = state.get("session_id", "SESSION-UNKNOWN")

        from personal_health.services.document_ingestion_service import DocumentIngestionService
        from personal_health.repositories.medical_document_repository import MedicalDocumentRepository

        doc_repo = MedicalDocumentRepository()
        ingestion_service = DocumentIngestionService(repository=doc_repo)

        document_paths = state.get("document_paths") or []
        medical_docs = list(state.get("medical_documents") or [])
        pending_records = list(state.get("pending_medical_records") or [])

        for doc_path in document_paths:
            p = Path(doc_path)
            if p.exists() and p.is_file():
                try:
                    file_bytes = p.read_bytes()
                    upload_res = ingestion_service.upload_document(
                        file_bytes=file_bytes,
                        filename=p.name,
                        astronaut_id=astronaut_id
                    )
                    proc_res = ingestion_service.process_document(upload_res.document_id)
                    medical_docs.append(proc_res.model_dump())
                    records_for_doc = doc_repo.get_records_by_document(upload_res.document_id)
                    for rfd in records_for_doc:
                        if not any(pr.get("record_id") == rfd.record_id for pr in pending_records if isinstance(pr, dict)):
                            pending_records.append({
                                "record_id": rfd.record_id,
                                "document_id": rfd.document_id,
                                "astronaut_id": rfd.astronaut_id,
                                "test_name": rfd.test_name,
                                "extracted_value": rfd.extracted_value,
                                "normalized_value": rfd.normalized_value,
                                "original_unit": rfd.original_unit,
                                "validation_status": rfd.validation_status
                            })
                except Exception as exc:
                    medical_docs.append({
                        "document_path": str(doc_path),
                        "status": "FAILED",
                        "error": str(exc)
                    })

        confirmed_records = list(state.get("confirmed_medical_records") or [])
        if astronaut_id and astronaut_id not in ("AST-UNKNOWN", "UNKNOWN"):
            existing_confirmed = doc_repo.get_confirmed_records(astronaut_id)
            for ec in existing_confirmed:
                ec_dict = ec.model_dump()
                if not any(r.get("record_id") == ec.record_id for r in confirmed_records if isinstance(r, dict)):
                    confirmed_records.append(ec_dict)

        existing = state.get("personal_health_result")
        if existing is not None:
            status = AgentExecutionStatus(
                agent_name=self.agent_name,
                status=AgentExecutionState.SUCCESS,
                warnings=["Used pre-existing Personal Health assessment from state."]
            )
            return {
                "personal_health_result": existing,
                "medical_documents": medical_docs,
                "pending_medical_records": pending_records,
                "confirmed_medical_records": confirmed_records
            }, status

        from personal_health.services.health_profile_service import HealthProfileService
        from personal_health.services.sensor_integration_service import SensorIntegrationService
        from personal_health.services.feature_extraction_service import FeatureExtractionService
        from personal_health.services.ml_inference_service import MLInferenceService
        from personal_health.services.symptom_service import SymptomService
        from personal_health.services.baseline_interface import PersonalBaselineInterface
        from personal_health.services.mission_context_service import MissionContextService
        from personal_health.services.rag_service import MedicalRAGService
        from personal_health.services.escalation_service import EmergencyEscalationService
        from personal_health.services.evidence_correlation_service import EvidenceCorrelationEngine
        from personal_health.agent.agent import generate_clinical_synthesis
        from personal_health.schemas.assessment import (
            PersonalHealthAssessment,
            AssessmentStatus,
            BaselineStatus,
            EscalationDetails
        )
        from personal_health.schemas.symptom_event import SymptomAssessmentStatus

        sensor_service = SensorIntegrationService(base_data_dir=cfg.sensor_quality_dir / "data")
        sqr_raw = state.get("sensor_quality_result") or state.get("sensor_quality_report")

        valid_streams = {}
        sensor_context = None

        if sqr_raw:
            try:
                sensor_context, valid_streams = sensor_service.ingest_session(
                    report_data=sqr_raw,
                    manifest_data=state.get("sensor_data")
                )
            except Exception as exc:
                sensor_context = None
                valid_streams = {}

        reported_symptoms = []
        clarification_requests = []
        symptom_service = SymptomService()

        voice_path = state.get("reported_symptoms_voice_path")
        if voice_path:
            v_event, v_clar, _ = symptom_service.process_voice_symptom(
                audio_file_path=voice_path,
                astronaut_id=astronaut_id,
                session_id=session_id,
                language=state.get("voice_language")
            )
            if v_event:
                reported_symptoms.append(v_event)
            if v_clar:
                clarification_requests.append(v_clar)

        text_symptom = state.get("reported_symptoms_text")
        if text_symptom:
            t_event, t_clar = symptom_service.process_text_symptom(
                text=text_symptom,
                astronaut_id=astronaut_id,
                session_id=session_id
            )
            if t_event:
                reported_symptoms.append(t_event)
            if t_clar:
                clarification_requests.append(t_clar)

        escalation_service = EmergencyEscalationService()
        escalation = escalation_service.evaluate_immediate_escalation(
            symptoms=reported_symptoms,
            telemetry_features=None,
            critical_sensors_available="ECG" in valid_streams,
            sensor_quality_valid=sensor_context.can_proceed if sensor_context else False
        )

        profile_service = HealthProfileService()
        health_profile = profile_service.get_or_create_profile(astronaut_id)

        mission_service = MissionContextService()
        mission_ctx = mission_service.get_mission_context(session_id)
        if state.get("mission_context"):
            from personal_health.schemas.mission_context import MissionContext
            mission_ctx = MissionContext.model_validate(state["mission_context"])

        baseline_service = PersonalBaselineInterface()
        baseline_stat = baseline_service.get_baseline_status(astronaut_id)

        feature_service = FeatureExtractionService()
        feature_report = feature_service.extract_features(
            streams=valid_streams,
            astronaut_id=astronaut_id,
            session_id=session_id
        )

        baseline_dev = None
        if feature_report.core_features:
            feat_dict = feature_report.core_features.to_feature_dict()
            if not escalation.required:
                escalation = escalation_service.evaluate_immediate_escalation(
                    symptoms=reported_symptoms,
                    telemetry_features=feat_dict,
                    critical_sensors_available="ECG" in valid_streams,
                    sensor_quality_valid=sensor_context.can_proceed if sensor_context else False
                )
            sqa_scores = {}
            if sqr_raw and isinstance(sqr_raw, dict):
                for s_n, s_info in sqr_raw.get("sensors", {}).items():
                    if isinstance(s_info, dict):
                        sqa_scores[s_n] = float(s_info.get("quality_score", 1.0))
            baseline_dev = baseline_service.evaluate_deviation(
                astronaut_id=astronaut_id,
                current_features=feat_dict,
                sqa_scores=sqa_scores
            )

        ml_service = MLInferenceService()
        ml_findings = []
        if feature_report.core_features:
            try:
                pred = ml_service.predict_stress(feature_report.core_features)
                ml_findings.append(pred)
            except Exception:
                pass

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
        elif not (sensor_context and sensor_context.can_proceed):
            assessment_status = AssessmentStatus.INSUFFICIENT_EVIDENCE

        briefing_context = (
            f"Astronaut: {astronaut_id} | Session: {session_id}\n"
            f"Overall Quality: {sensor_context.overall_quality_score if sensor_context else 0.0:.3f}\n"
            f"Core Features Extracted: {feature_report.has_valid_core14}\n"
            f"ML Stress Verdict: {primary_ml.verdict if primary_ml else 'N/A'}\n"
            f"Reported Symptoms Count: {len(reported_symptoms)}\n"
            f"Escalation Required: {escalation.required} [Status: {escalation.status.value}]\n"
            f"Evidence Conflicts: {len(conflicts)}"
        )

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
            "mission_day": mission_ctx.microgravity_exposure_days if mission_ctx and mission_ctx.is_context_supplied else None,
            "has_clinical_fluid_shift_evidence": False,
            "symptom_count": len(reported_symptoms),
            "symptom_confirmed_negative": False,
            "baseline_status": baseline_stat.value,
            "has_resp_measurement": "RESP" in valid_streams,
            "has_acc_measurement": "ACC" in valid_streams,
        }

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
            personal_baseline_deviation=baseline_dev,
            sensor_quality_summary=sensor_context,
            core_features=feature_report.core_features,
            physiological_findings=feature_report.all_features,
            hrv_diagnostics=feature_report.hrv_diagnostics,
            ml_findings=ml_findings,
            symptom_findings=reported_symptoms,
            symptom_assessment_status=symptom_status,
            health_profile_summary={
                "age": health_profile.basic_info.age if health_profile else None,
                "resting_hr": health_profile.physical_fitness.resting_heart_rate_bpm if health_profile else None
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

        exec_state = AgentExecutionState.SUCCESS if assessment_status == AssessmentStatus.COMPLETED else AgentExecutionState.PARTIAL
        status = AgentExecutionStatus(
            agent_name=self.agent_name,
            status=exec_state,
            warnings=uncertainties
        )

        return {
            "personal_health_result": assessment.model_dump(),
            "personal_health_assessment": assessment.model_dump(),
            "personal_baseline_deviation": baseline_dev,
            "medical_documents": medical_docs,
            "pending_medical_records": pending_records,
            "confirmed_medical_records": confirmed_records
        }, status
