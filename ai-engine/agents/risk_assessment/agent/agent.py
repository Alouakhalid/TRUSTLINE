"""Central coordinator for the TRUSTLINE Risk Assessment Agent and LangGraph integration."""
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..schemas.risk_input import RiskAssessmentInput
from ..schemas.risk_output import (
    RiskAssessmentOutput,
    ProtocolReference
)
from ..schemas.risk_rules import RiskLevel, RiskConfidence, EscalationState
from ..services.input_validation_service import InputValidationService
from ..services.evidence_normalization_service import EvidenceNormalizationService
from ..services.evidence_correlation_service import EvidenceCorrelationService
from ..services.risk_engine import RiskEngine
from ..services.escalation_service import RiskEscalationService
from ..services.llm_interpretation_service import LLMInterpretationService

class RiskAssessmentAgent:
    """Specialized agent synthesizing evidence, evaluating deterministic risk rules, and recommending escalation."""

    def __init__(
        self,
        risk_engine: Optional[RiskEngine] = None,
        llm_service: Optional[LLMInterpretationService] = None
    ):
        self.validation_service = InputValidationService()
        self.normalization_service = EvidenceNormalizationService()
        self.correlation_service = EvidenceCorrelationService()
        self.risk_engine = risk_engine or RiskEngine()
        self.llm_service = llm_service or LLMInterpretationService()

    def assess(self, payload: RiskAssessmentInput) -> RiskAssessmentOutput:
        """Execute complete, evidence-grounded risk assessment pipeline."""
        is_valid, val_errors, val_warnings = self.validation_service.validate_input(payload)
        if not is_valid:
            failed_esc, failed_acts = RiskEscalationService.determine_escalation(
                triggered_rules=[],
                overall_risk=RiskLevel.UNKNOWN,
                evidence_items=[],
                upstream_escalation_required=False
            )
            failed_esc.state = EscalationState.ASSESSMENT_FAILED
            failed_esc.reason = f"Input validation failed: {'; '.join(val_errors)}"

            return RiskAssessmentOutput(
                assessment_id=payload.assessment_id,
                astronaut_id=payload.astronaut_id,
                session_id=payload.session_id,
                assessment_status="PROCESSING_FAILED",
                overall_risk=RiskLevel.UNKNOWN,
                overall_confidence=RiskConfidence.UNDETERMINED,
                uncertainties=val_errors,
                missing_information=["Valid input payload satisfying schema requirements"],
                escalation=failed_esc,
                recommended_actions=failed_acts,
                requires_human_review=True,
                processing_metadata={"validation_errors": val_errors, "validation_warnings": val_warnings},
                llm_explanation="Risk assessment could not be processed due to upstream schema validation failure.",
                llm_status="LLM_SKIPPED"
            )

        evidence_items = self.normalization_service.normalize_all(payload)

        correlations = self.correlation_service.evaluate_correlations(evidence_items)

        eval_res = self.risk_engine.evaluate_risks(evidence_items)

        upstream_esc_req = False
        upstream_reason = None
        if payload.personal_health_assessment is not None:
            up_esc = payload.personal_health_assessment.escalation
            if up_esc.required or up_esc.status.value == "ESCALATION_REQUIRED":
                upstream_esc_req = True
                upstream_reason = "; ".join(up_esc.triggers) if up_esc.triggers else "Personal Health red-line trigger"

        escalation_details, recommended_actions = RiskEscalationService.determine_escalation(
            triggered_rules=eval_res.triggered_rules,
            overall_risk=eval_res.overall_risk,
            evidence_items=evidence_items,
            upstream_escalation_required=upstream_esc_req,
            upstream_reason=upstream_reason
        )

        domain_dicts = [
            {
                "domain": d.domain.value,
                "risk_level": d.risk_level.value,
                "confidence": d.confidence.value,
                "explanation": d.explanation
            }
            for d in eval_res.domain_assessments
        ]
        concern_dicts = [
            {
                "title": c.title,
                "severity": c.severity.value,
                "description": c.description,
                "supporting_evidence_ids": c.supporting_evidence_ids
            }
            for c in eval_res.concerns
        ]

        mission_day_supplied = bool(
            payload.mission_context is not None and payload.mission_context.mission_elapsed_time_hours is not None
        )

        sym_denied = any(p.factor_id == "PROT-SYM-DENIAL-01" for p in eval_res.protective_factor_details)
        allowed_prot_doms = [p.domain.value for p in eval_res.protective_factor_details]
        ev_dom_names = [d.value for d in eval_res.coverage.evaluated_domains]
        unev_dom_names = [d.value for d in eval_res.coverage.unevaluated_domains]

        symptoms_submitted = bool(
            payload.reported_symptoms
            or (payload.personal_health_assessment and payload.personal_health_assessment.symptom_findings)
            or sym_denied
        )

        discordant_correlations = [c["summary"] for c in correlations if not c.get("is_concordant", True)]
        all_uncertainties = eval_res.uncertainties + val_warnings + discordant_correlations

        rec_action_dicts = [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "description": a.description,
                "priority": a.priority,
                "destination": a.destination.value if hasattr(a.destination, "value") else str(a.destination)
            }
            for a in recommended_actions
        ]

        llm_text, llm_status = self.llm_service.generate_explanation(
            astronaut_id=payload.astronaut_id,
            session_id=payload.session_id,
            overall_risk=eval_res.overall_risk,
            overall_confidence=eval_res.overall_confidence.value,
            escalation_state=escalation_details.state,
            escalation_reason=escalation_details.reason,
            domain_summaries=domain_dicts,
            concerns=concern_dicts,
            protective_factors=eval_res.protective_factors,
            uncertainties=all_uncertainties,
            missing_info=eval_res.missing_info,
            mission_day_supplied=mission_day_supplied,
            assessment_status=eval_res.assessment_status,
            coverage_ratio=eval_res.coverage.domain_coverage_ratio,
            evaluated_domains=ev_dom_names,
            unevaluated_domains=unev_dom_names,
            symptoms_explicitly_denied=sym_denied,
            allowed_protective_domains=allowed_prot_doms,
            symptoms_submitted=symptoms_submitted,
            nominal_observations=eval_res.nominal_observations,
            recommended_actions=rec_action_dicts
        )

        protocols: List[ProtocolReference] = []
        for r in eval_res.triggered_rules:
            protocols.append(
                ProtocolReference(
                    protocol_id=r.rule_id,
                    title=r.rule_name,
                    source_organization=r.rule_source,
                    relevance_summary=r.rationale
                )
            )

        req_review = (
            eval_res.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            or escalation_details.state in (EscalationState.REVIEW_REQUIRED, EscalationState.ESCALATION_RECOMMENDED, EscalationState.ESCALATION_REQUIRED)
            or any(d.requires_human_review for d in eval_res.domain_assessments)
        )

        return RiskAssessmentOutput(
            assessment_id=payload.assessment_id,
            astronaut_id=payload.astronaut_id,
            session_id=payload.session_id,
            assessment_timestamp=datetime.utcnow(),
            assessment_status=eval_res.assessment_status,
            evaluated_domains_risk=eval_res.evaluated_domains_risk,
            overall_risk=eval_res.overall_risk,
            overall_confidence=eval_res.overall_confidence,
            coverage=eval_res.coverage,
            risk_domains=eval_res.domain_assessments,
            identified_concerns=eval_res.concerns,
            evidence_summary=eval_res.evidence_summary,
            triggered_rules=eval_res.triggered_rules,
            non_triggered_rules=eval_res.non_triggered_rules,
            uncertainties=all_uncertainties,
            missing_information=eval_res.missing_info,
            nominal_observation_details=eval_res.nominal_observation_details,
            nominal_observations=eval_res.nominal_observations,
            protective_factor_details=eval_res.protective_factor_details,
            protective_factors=eval_res.protective_factors,
            escalation=escalation_details,
            recommended_actions=recommended_actions,
            protocol_references=protocols,
            requires_human_review=req_review,
            processing_metadata={
                "normalized_evidence_count": len(evidence_items),
                "correlations_identified": len(correlations),
                "triggered_rules_count": len(eval_res.triggered_rules),
                "validation_warnings": val_warnings,
                "correlations": correlations,
                "coverage_status": eval_res.coverage.coverage_status
            },
            llm_explanation=llm_text,
            llm_status=llm_status
        )

def risk_assessment_langgraph_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node callable ingesting multi-agent state and appending Risk Assessment output."""
    agent = RiskAssessmentAgent()

    astro_id = state.get("astronaut_id", "AST-UNKNOWN")
    session_id = state.get("session_id", "SESSION-UNKNOWN")

    sqr_raw = state.get("sensor_quality_report")
    sqr_obj = None
    if sqr_raw is not None:
        from sensor_quality.schemas.output_schema import SensorQualityReport
        sqr_obj = SensorQualityReport.model_validate(sqr_raw) if isinstance(sqr_raw, dict) else sqr_raw

    pha_raw = state.get("personal_health_assessment")
    pha_obj = None
    if pha_raw is not None:
        from personal_health.schemas.assessment import PersonalHealthAssessment
        pha_obj = PersonalHealthAssessment.model_validate(pha_raw) if isinstance(pha_raw, dict) else pha_raw

    confirmed_raw = state.get("confirmed_medical_records", [])
    from personal_health.schemas.medical_document import ConfirmedMedicalFinding
    confirmed_objs = [
        ConfirmedMedicalFinding.model_validate(r) if isinstance(r, dict) else r
        for r in confirmed_raw
    ]

    ctx_raw = state.get("mission_context")
    ctx_obj = None
    if ctx_raw is not None:
        from personal_health.schemas.mission_context import MissionContext
        ctx_obj = MissionContext.model_validate(ctx_raw) if isinstance(ctx_raw, dict) else ctx_raw

    input_payload = RiskAssessmentInput(
        astronaut_id=astro_id,
        session_id=session_id,
        sensor_quality_report=sqr_obj,
        personal_health_assessment=pha_obj,
        confirmed_medical_records=confirmed_objs,
        mission_context=ctx_obj
    )

    result = agent.assess(input_payload)

    return {
        "risk_assessment_output": result.model_dump(),
        "overall_risk": result.overall_risk.value,
        "evaluated_domains_risk": result.evaluated_domains_risk.value,
        "assessment_status": result.assessment_status,
        "domain_coverage_ratio": result.coverage.domain_coverage_ratio if result.coverage else 0.0,
        "escalation_state": result.escalation.state.value,
        "requires_human_review": result.requires_human_review,
        "current_step": "SUPERVISOR_COMPILATION"
    }
