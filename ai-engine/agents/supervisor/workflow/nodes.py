"""LangGraph node implementations for TRUSTLINE Supervisor Agent."""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from ..schemas.state import SupervisorMultiAgentState
from ..schemas.assessment import (
    WorkflowCompletionStatus,
    AgentExecutionState,
    AgentExecutionStatus,
    EvidenceRegistryItem,
    CoverageSummary,
    WorkflowTimingBreakdown,
    FinalSupervisorAssessment
)
from ..adapters.sensor_quality_adapter import SensorQualityAdapter
from ..adapters.personal_health_adapter import PersonalHealthAdapter
from ..adapters.risk_assessment_adapter import RiskAssessmentAdapter
from ..services.evidence_registry_service import EvidenceRegistryService
from ..services.astronaut_communication_service import AstronautCommunicationService
from ..services.persistence_service import PersistenceService

def intake_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Initialize workflow execution state, generate tracking identifiers, and record start timestamp."""
    wf_id = state.get("workflow_id") or f"WF-{uuid.uuid4().hex[:8].upper()}"
    timestamps = dict(state.get("timestamps") or {})
    timestamps["intake"] = datetime.utcnow().isoformat()

    agent_statuses = dict(state.get("agent_execution_status") or {})
    agent_statuses["supervisor"] = AgentExecutionStatus(
        agent_name="supervisor_orchestrator",
        status=AgentExecutionState.SUCCESS,
        warnings=[]
    ).model_dump()

    return {
        "workflow_id": wf_id,
        "workflow_status": "IN_PROGRESS",
        "current_step": "INTAKE",
        "agent_execution_status": agent_statuses,
        "timestamps": timestamps,
        "errors": list(state.get("errors") or []),
        "warnings": list(state.get("warnings") or []),
        "missing_data": list(state.get("missing_data") or [])
    }

def input_validation_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Validate subject identity, manifest path, and security constraints before dispatching agents."""
    errors = list(state.get("errors") or [])
    warnings = list(state.get("warnings") or [])
    missing_data = list(state.get("missing_data") or [])

    astro_id = state.get("astronaut_id", "").strip()
    session_id = state.get("session_id", "").strip()

    if not astro_id or astro_id == "AST-UNKNOWN":
        errors.append("Validation Failure: Missing or invalid astronaut_id.")
    if not session_id or session_id == "SESSION-UNKNOWN":
        errors.append("Validation Failure: Missing or invalid session_id.")

    manifest_path = state.get("manifest_path")
    raw_manifest = state.get("sensor_data")
    if not manifest_path and not raw_manifest:
        missing_data.append("Sensor telemetry manifest was not provided for this session.")

    if not state.get("reported_symptoms_text") and not state.get("reported_symptoms_voice_path"):
        missing_data.append("Subjective symptom questionnaire was not submitted.")

    if not state.get("confirmed_medical_records"):
        missing_data.append("External confirmed medical records were not submitted.")

    if not state.get("mission_context"):
        missing_data.append("Mission operational context parameters were not provided.")

    if errors:
        return {
            "workflow_status": "FAILED",
            "current_step": "INPUT_VALIDATION_FAILED",
            "errors": errors,
            "warnings": warnings,
            "missing_data": missing_data
        }

    return {
        "current_step": "INPUT_VALIDATION",
        "errors": errors,
        "warnings": warnings,
        "missing_data": missing_data
    }

def sensor_quality_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Execute Sensor Quality Agent adapter and capture execution telemetry."""
    adapter = SensorQualityAdapter()
    updates, status = adapter.execute_with_telemetry(state)

    agent_statuses = dict(state.get("agent_execution_status") or {})
    agent_statuses["sensor_quality_agent"] = status.model_dump()

    warnings = list(state.get("warnings") or [])
    warnings.extend(status.warnings)

    errors = list(state.get("errors") or [])
    if status.error_message:
        errors.append(f"Sensor Quality Error: {status.error_message}")

    updates["agent_execution_status"] = agent_statuses
    updates["warnings"] = warnings
    updates["errors"] = errors
    updates["current_step"] = "SENSOR_QUALITY"

    return updates

def personal_health_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Execute Personal Health Agent adapter and capture execution telemetry."""
    adapter = PersonalHealthAdapter()
    updates, status = adapter.execute_with_telemetry(state)

    agent_statuses = dict(state.get("agent_execution_status") or {})
    agent_statuses["personal_health_agent"] = status.model_dump()

    warnings = list(state.get("warnings") or [])
    warnings.extend(status.warnings)

    errors = list(state.get("errors") or [])
    if status.error_message:
        errors.append(f"Personal Health Error: {status.error_message}")

    updates["agent_execution_status"] = agent_statuses
    updates["warnings"] = warnings
    updates["errors"] = errors
    updates["current_step"] = "PERSONAL_HEALTH"

    return updates

def risk_assessment_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Execute Risk Assessment Agent adapter and capture execution telemetry."""
    adapter = RiskAssessmentAdapter()
    updates, status = adapter.execute_with_telemetry(state)

    agent_statuses = dict(state.get("agent_execution_status") or {})
    agent_statuses["risk_assessment_agent"] = status.model_dump()

    warnings = list(state.get("warnings") or [])
    warnings.extend(status.warnings)

    errors = list(state.get("errors") or [])
    if status.error_message:
        errors.append(f"Risk Assessment Error: {status.error_message}")

    updates["agent_execution_status"] = agent_statuses
    updates["warnings"] = warnings
    updates["errors"] = errors
    updates["current_step"] = "RISK_ASSESSMENT"

    return updates

def evidence_validation_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Compile cross-agent evidence registry and verify quarantine guards on invalid artifacts."""
    t_start = datetime.utcnow()
    registry_items = EvidenceRegistryService.compile_and_audit_registry(state)
    registry_dicts = [item.model_dump() for item in registry_items]

    quarantined_count = sum(1 for item in registry_items if item.is_quarantined)
    warnings = list(state.get("warnings") or [])
    if quarantined_count > 0:
        warnings.append(f"Evidence Registry: {quarantined_count} evidence item(s) quarantined under scientific integrity guards.")

    durations = dict(state.get("durations_ms") or {})
    durations["evidence_validation"] = max(0.1, (datetime.utcnow() - t_start).total_seconds() * 1000.0)

    return {
        "evidence_registry": registry_dicts,
        "warnings": warnings,
        "durations_ms": durations,
        "current_step": "EVIDENCE_VALIDATION"
    }

def final_synthesis_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Synthesize complete multi-agent assessment and compile FinalSupervisorAssessment contract."""
    t_start = datetime.utcnow()
    astro_id = state.get("astronaut_id", "AST-UNKNOWN")
    session_id = state.get("session_id", "SESSION-UNKNOWN")
    wf_id = state.get("workflow_id", "WF-UNKNOWN")

    sqr = state.get("sensor_quality_result") or {}
    pha = state.get("personal_health_result") or {}
    ra = state.get("risk_assessment_result") or {}

    agent_statuses_raw = state.get("agent_execution_status") or {}
    agent_statuses = {}
    for k, v in agent_statuses_raw.items():
        agent_statuses[k] = AgentExecutionStatus.model_validate(v) if isinstance(v, dict) else v

    intake_ts_str = (state.get("timestamps") or {}).get("intake")
    if intake_ts_str:
        try:
            start_dt = datetime.fromisoformat(intake_ts_str)
            total_elapsed_ms = max(0.1, (datetime.utcnow() - start_dt).total_seconds() * 1000.0)
        except Exception:
            total_elapsed_ms = 0.0
    else:
        total_elapsed_ms = 0.0

    sq_ms = float(agent_statuses.get("sensor_quality_agent", {}).execution_time_ms if "sensor_quality_agent" in agent_statuses else 0.0)
    pha_ms = float(agent_statuses.get("personal_health_agent", {}).execution_time_ms if "personal_health_agent" in agent_statuses else 0.0)
    ra_ms = float(agent_statuses.get("risk_assessment_agent", {}).execution_time_ms if "risk_assessment_agent" in agent_statuses else 0.0)

    subagent_total_ms = sq_ms + pha_ms + ra_ms
    supervisor_overhead_ms = max(0.1, round(total_elapsed_ms - subagent_total_ms, 2))

    if "supervisor" in agent_statuses:
        agent_statuses["supervisor"].execution_time_ms = supervisor_overhead_ms
    else:
        agent_statuses["supervisor"] = AgentExecutionStatus(
            agent_name="supervisor_orchestrator",
            status=AgentExecutionState.SUCCESS,
            execution_time_ms=supervisor_overhead_ms,
            warnings=[]
        )

    coverage_raw = ra.get("coverage") or {}
    coverage = CoverageSummary(
        total_domains=coverage_raw.get("total_domains", 10),
        evaluated_domains=coverage_raw.get("evaluated_domains", []),
        unevaluated_domains=coverage_raw.get("unevaluated_domains", []),
        partially_evaluated_domains=coverage_raw.get("partially_evaluated_domains", []),
        domain_coverage_ratio=coverage_raw.get("domain_coverage_ratio", 0.0),
        coverage_status=coverage_raw.get("coverage_status", "INSUFFICIENT")
    )

    esc_details = ra.get("escalation") or {}
    esc_state = esc_details.get("state", "NO_TRIGGER_DETECTED")
    esc_req = esc_details.get("required", False)
    esc_urg = esc_details.get("urgency_level", "NOMINAL")

    overall_risk = ra.get("overall_risk", "INSUFFICIENT_DATA")
    overall_conf = ra.get("overall_confidence", "MODERATE")
    overall_status = ra.get("assessment_status", "PARTIALLY_COMPLETED")

    errors = list(state.get("errors") or [])
    if errors and not (sqr or pha or ra):
        completion_status = WorkflowCompletionStatus.FAILED
    elif errors or coverage.domain_coverage_ratio < 1.0 or overall_status == "PARTIALLY_COMPLETED":
        completion_status = WorkflowCompletionStatus.PARTIALLY_COMPLETED
    else:
        completion_status = WorkflowCompletionStatus.COMPLETED

    concerns = ra.get("identified_concerns", [])
    nominals = ra.get("nominal_observation_details", [])
    protectives = ra.get("protective_factor_details", [])
    uncertainties = list(ra.get("uncertainties", []))
    missing_info = list(ra.get("missing_information", []))
    rec_actions = ra.get("recommended_actions", [])

    for m in state.get("missing_data", []):
        if m not in missing_info:
            missing_info.append(m)

    evidence_items = [
        EvidenceRegistryItem.model_validate(e) if isinstance(e, dict) else e
        for e in state.get("evidence_registry", [])
    ]

    executive_synthesis = ra.get("llm_explanation") or pha.get("llm_executive_synthesis")

    user_query = None
    incoming = state.get("incoming_request") or {}
    input_data = incoming.get("input_data") or {}
    if isinstance(input_data, dict):
        user_query = input_data.get("text_query")

    symptoms_reported = pha.get("symptom_findings", [])
    core_features = pha.get("core_features") or {}

    astronaut_response = AstronautCommunicationService.generate_astronaut_response(
        astronaut_id=astro_id,
        session_id=session_id,
        overall_risk=overall_risk,
        escalation_state=esc_state,
        escalation_required=esc_req,
        coverage_ratio=coverage.domain_coverage_ratio,
        evaluated_domains=coverage.evaluated_domains,
        unevaluated_domains=coverage.unevaluated_domains,
        recommended_actions=rec_actions,
        user_query=user_query,
        symptoms_reported=symptoms_reported,
        core_features=core_features,
        evidence_items=evidence_items
    )

    durations = dict(state.get("durations_ms") or {})
    synthesis_dur = max(0.1, (datetime.utcnow() - t_start).total_seconds() * 1000.0)
    durations["final_synthesis"] = synthesis_dur

    timing_breakdown = WorkflowTimingBreakdown(
        workflow_total_execution_time_ms=round(total_elapsed_ms, 2),
        supervisor_overhead_time_ms=round(supervisor_overhead_ms, 2),
        sensor_quality_execution_time_ms=round(sq_ms, 2),
        personal_health_execution_time_ms=round(pha_ms, 2),
        risk_assessment_execution_time_ms=round(ra_ms, 2),
        evidence_validation_time_ms=round(durations.get("evidence_validation", 0.0), 2),
        final_synthesis_time_ms=round(synthesis_dur, 2),
        persistence_time_ms=round(durations.get("persistence", 0.0), 2)
    )

    assessment = FinalSupervisorAssessment(
        assessment_id=f"SUP-{uuid.uuid4().hex[:8].upper()}",
        astronaut_id=astro_id,
        session_id=session_id,
        workflow_id=wf_id,
        generation_timestamp=datetime.utcnow(),
        workflow_completion_status=completion_status,
        agent_execution_statuses=agent_statuses,
        timing_breakdown=timing_breakdown,
        overall_assessment_status=overall_status,
        overall_risk=overall_risk,
        overall_confidence=overall_conf,
        escalation_state=esc_state,
        escalation_required=esc_req,
        escalation_urgency=esc_urg,
        coverage_summary=coverage,
        sensor_quality_summary=sqr,
        personal_health_summary=pha,
        risk_assessment_summary=ra,
        detected_concerns=concerns,
        nominal_observations=nominals,
        protective_factors=protectives,
        uncertainties=uncertainties,
        missing_information=missing_info,
        recommended_actions=rec_actions,
        evidence_references=evidence_items,
        provenance_chain=[
            {"agent": "sensor_quality_agent", "status": agent_statuses.get("sensor_quality_agent", {}).status if "sensor_quality_agent" in agent_statuses else "SKIPPED"},
            {"agent": "personal_health_agent", "status": agent_statuses.get("personal_health_agent", {}).status if "personal_health_agent" in agent_statuses else "SKIPPED"},
            {"agent": "risk_assessment_agent", "status": agent_statuses.get("risk_assessment_agent", {}).status if "risk_assessment_agent" in agent_statuses else "SKIPPED"}
        ],
        executive_synthesis=executive_synthesis,
        astronaut_facing_response=astronaut_response
    )

    return {
        "final_assessment": assessment.model_dump(),
        "final_response": astronaut_response,
        "workflow_status": completion_status.value,
        "agent_execution_status": {k: v.model_dump() if hasattr(v, "model_dump") else v for k, v in agent_statuses.items()},
        "durations_ms": durations,
        "current_step": "FINAL_SYNTHESIS"
    }

def persistence_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Persist final assessment to disk and edge SQLite database."""
    t_start = datetime.utcnow()
    assessment_dict = state.get("final_assessment") or {}
    success, filepath, p_warnings = PersistenceService.save_final_assessment(assessment_dict)

    warnings = list(state.get("warnings") or [])
    warnings.extend(p_warnings)

    errors = list(state.get("errors") or [])
    workflow_status = state.get("workflow_status")
    if not success:
        errors.append("Persistence Failure: Failed to write assessment artifact or edge database record.")
        if workflow_status == "COMPLETED":
            workflow_status = "PARTIALLY_COMPLETED"

    durations = dict(state.get("durations_ms") or {})
    durations["persistence"] = max(0.1, (datetime.utcnow() - t_start).total_seconds() * 1000.0)

    return {
        "warnings": warnings,
        "errors": errors,
        "workflow_status": workflow_status,
        "durations_ms": durations,
        "current_step": "PERSISTENCE"
    }

def final_response_node(state: SupervisorMultiAgentState) -> Dict[str, Any]:
    """Finalize workflow, stamp completion timestamp, and deliver astronaut communication."""
    timestamps = dict(state.get("timestamps") or {})
    timestamps["completed"] = datetime.utcnow().isoformat()

    return {
        "timestamps": timestamps,
        "current_step": "FINAL_RESPONSE"
    }
