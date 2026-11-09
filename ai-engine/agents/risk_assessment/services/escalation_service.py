"""Deterministic escalation state machine governing clinical and mission operational alerts."""
from typing import Dict, List, Optional, Tuple, Any
from ..schemas.evidence import RiskDomain, EvidenceValidity, NormalizedEvidenceItem
from ..schemas.risk_rules import (
    RiskLevel,
    EscalationState,
    EscalationDestination,
    TriggeredRuleDetail
)
from ..schemas.risk_output import (
    RiskEscalationDetails,
    RecommendedAction
)

class RiskEscalationService:
    """Evaluates escalation eligibility deterministically based on triggered rules and safety invariants."""

    @classmethod
    def determine_escalation(
        cls,
        triggered_rules: List[TriggeredRuleDetail],
        overall_risk: RiskLevel,
        evidence_items: List[NormalizedEvidenceItem],
        upstream_escalation_required: bool = False,
        upstream_reason: Optional[str] = None
    ) -> Tuple[RiskEscalationDetails, List[RecommendedAction]]:
        """Evaluate escalation state, urgency, supporting rules, and actionable recommendations."""
        actions: List[RecommendedAction] = []
        rule_ids = [r.rule_id for r in triggered_rules]

        if any(r.suggested_escalation == EscalationState.ESCALATION_REQUIRED for r in triggered_rules) or upstream_escalation_required:
            state = EscalationState.ESCALATION_REQUIRED
            required = True
            urgency = "CRITICAL"
            destination = EscalationDestination.EMERGENCY_MEDICAL_RESPONSE
            reason = (
                f"Mandatory escalation triggered by red-line protocol rule(s): {', '.join(rule_ids)}."
                if rule_ids else f"Mandatory escalation triggered upstream: {upstream_reason or 'Emergency red-line'}"
            )
            immediate_acts = [
                "Transmit immediate high-priority emergency telemetry alert to Flight Surgeon console",
                "Instruct astronaut to immediately cease activity, rest in seated or supine position",
                "Stand by for Crew Medical Restraint System (CMRS) deployment if hemodynamic compromise develops"
            ]

            actions.append(
                RecommendedAction(
                    action_id="ACT-EMERG-001",
                    action_type="CMRS_DEPLOYMENT",
                    description="Stand by for emergency clinical assessment and medical diagnostic kit deployment.",
                    reason="Satisfies mandatory ISS-MEDOPS-REDLINE criteria.",
                    supporting_rule_ids=rule_ids,
                    supporting_evidence_ids=list(set(ev for r in triggered_rules for ev in r.supporting_evidence_ids)),
                    destination=EscalationDestination.EMERGENCY_MEDICAL_RESPONSE,
                    priority="CRITICAL",
                    requires_human_authorization=False
                )
            )

        elif any(r.suggested_escalation == EscalationState.ESCALATION_RECOMMENDED for r in triggered_rules):
            state = EscalationState.ESCALATION_RECOMMENDED
            required = False
            urgency = "URGENT"
            destination = EscalationDestination.FLIGHT_SURGEON
            reason = f"Clinical escalation recommended based on operational rule(s): {', '.join(rule_ids)}."
            immediate_acts = [
                "Notify Flight Surgeon during next scheduled communications pass",
                "Request targeted follow-up telemetry check"
            ]

            actions.append(
                RecommendedAction(
                    action_id="ACT-REC-001",
                    action_type="CLINICAL_REVIEW",
                    description="Flight Surgeon review of documented physiological elevation.",
                    reason="Precautionary clinical evaluation advised per approved protocol.",
                    supporting_rule_ids=rule_ids,
                    supporting_evidence_ids=list(set(ev for r in triggered_rules for ev in r.supporting_evidence_ids)),
                    destination=EscalationDestination.FLIGHT_SURGEON,
                    priority="URGENT",
                    requires_human_authorization=True
                )
            )

        elif any(r.suggested_escalation == EscalationState.REVIEW_REQUIRED for r in triggered_rules):
            state = EscalationState.REVIEW_REQUIRED
            required = False
            urgency = "ELEVATED"
            destination = EscalationDestination.FLIGHT_SURGEON
            reason = f"Human review required due to detected parameter elevation or data quality anomaly: {', '.join(rule_ids)}."
            immediate_acts = [
                "Schedule routine telemetry review by medical operations",
                "Verify sensor coupling if data quality anomaly was identified"
            ]

            actions.append(
                RecommendedAction(
                    action_id="ACT-REV-001",
                    action_type="MONITORING",
                    description="Log parameter for routine Flight Surgeon trending and sensor check.",
                    reason="Telemetry deviation noted without immediate red-line breach.",
                    supporting_rule_ids=rule_ids,
                    supporting_evidence_ids=list(set(ev for r in triggered_rules for ev in r.supporting_evidence_ids)),
                    destination=EscalationDestination.FLIGHT_SURGEON,
                    priority="ROUTINE",
                    requires_human_authorization=True
                )
            )

        elif overall_risk == RiskLevel.INSUFFICIENT_DATA and not any(e.validity_status == EvidenceValidity.VALID for e in evidence_items):
            state = EscalationState.INSUFFICIENT_DATA
            required = False
            urgency = "ELEVATED"
            destination = EscalationDestination.FLIGHT_SURGEON
            reason = "Insufficient valid telemetry available to evaluate safety rules."
            immediate_acts = [
                "Instruct astronaut to inspect and readjust sensor electrodes and connections",
                "Re-acquire telemetry baseline prior to operational tasks"
            ]

            actions.append(
                RecommendedAction(
                    action_id="ACT-DATA-001",
                    action_type="RECALIBRATION",
                    description="Inspect physiological sensor placement and re-verify signal integrity.",
                    reason="Telemetry classified as INVALID by Sensor Quality Agent.",
                    destination=EscalationDestination.ASTRONAUT_SELF_MONITORING,
                    priority="URGENT",
                    requires_human_authorization=False
                )
            )

        else:
            state = EscalationState.NO_TRIGGER_DETECTED
            required = False
            urgency = "NOMINAL"
            destination = EscalationDestination.ASTRONAUT_SELF_MONITORING
            reason = (
                "No configured escalation rule triggered using available valid evidence. "
                "Notice: This finding indicates no configured emergency rule was met; it does not confirm clinical absence of disease, "
                "complete assessment coverage, or nominal physiological status across unassessed domains."
            )
            immediate_acts = [
                "Continue standard routine in-flight telemetry monitoring for evaluated parameters"
            ]

            actions.append(
                RecommendedAction(
                    action_id="ACT-NOM-001",
                    action_type="MONITORING",
                    description="Continue routine health telemetry acquisition for monitored parameters.",
                    reason="All observed parameters in evaluated streams within nominal reference boundaries. Unassessed domains require separate monitoring.",
                    destination=EscalationDestination.ASTRONAUT_SELF_MONITORING,
                    priority="ROUTINE",
                    requires_human_authorization=False
                )
            )

        escalation_details = RiskEscalationDetails(
            state=state,
            required=required,
            urgency_level=urgency,
            reason=reason,
            supporting_rule_ids=rule_ids,
            destination=destination,
            immediate_actions=immediate_acts
        )

        return escalation_details, actions
