"""Risk Assessment Agent adapter orchestrating deterministic multi-domain evaluation."""
from typing import Dict, Any, Tuple
from .base import BaseAgentAdapter
from ..schemas.assessment import AgentExecutionState, AgentExecutionStatus

class RiskAssessmentAdapter(BaseAgentAdapter):
    """Adapter invoking Risk Assessment Agent and mapping outputs to supervisor state."""

    def __init__(self):
        super().__init__(agent_name="risk_assessment_agent")

    def run(self, state: Dict[str, Any]) -> Tuple[Dict[str, Any], AgentExecutionStatus]:
        existing = state.get("risk_assessment_result")
        if existing is not None:
            status = AgentExecutionStatus(
                agent_name=self.agent_name,
                status=AgentExecutionState.SUCCESS,
                warnings=["Used pre-existing Risk Assessment report from state."]
            )
            return {"risk_assessment_result": existing}, status

        from risk_assessment.schemas.risk_input import RiskAssessmentInput
        from risk_assessment.agent.agent import RiskAssessmentAgent
        from sensor_quality.schemas.output_schema import SensorQualityReport
        from personal_health.schemas.assessment import PersonalHealthAssessment
        from personal_health.schemas.medical_document import ConfirmedMedicalFinding
        from personal_health.schemas.mission_context import MissionContext

        astronaut_id = state.get("astronaut_id", "AST-UNKNOWN")
        session_id = state.get("session_id", "SESSION-UNKNOWN")

        sqr_raw = state.get("sensor_quality_result") or state.get("sensor_quality_report")
        sqr_obj = SensorQualityReport.model_validate(sqr_raw) if sqr_raw else None

        pha_raw = state.get("personal_health_result") or state.get("personal_health_assessment")
        pha_obj = PersonalHealthAssessment.model_validate(pha_raw) if pha_raw else None

        confirmed_raw = state.get("confirmed_medical_records", [])
        confirmed_objs = [
            ConfirmedMedicalFinding.model_validate(r) if isinstance(r, dict) else r
            for r in confirmed_raw
        ]

        ctx_raw = state.get("mission_context")
        ctx_obj = MissionContext.model_validate(ctx_raw) if ctx_raw else None

        input_payload = RiskAssessmentInput(
            astronaut_id=astronaut_id,
            session_id=session_id,
            sensor_quality_report=sqr_obj,
            personal_health_assessment=pha_obj,
            confirmed_medical_records=confirmed_objs,
            mission_context=ctx_obj
        )

        agent = RiskAssessmentAgent()
        output = agent.assess(input_payload)

        if output.assessment_status in ("COMPLETED", "PARTIALLY_COMPLETED"):
            exec_state = AgentExecutionState.SUCCESS
        elif output.assessment_status == "INSUFFICIENT_DATA":
            exec_state = AgentExecutionState.PARTIAL
        else:
            exec_state = AgentExecutionState.FAILED
        warnings = list(output.uncertainties)

        status = AgentExecutionStatus(
            agent_name=self.agent_name,
            status=exec_state,
            warnings=warnings
        )

        return {
            "risk_assessment_result": output.model_dump(),
            "risk_assessment_output": output.model_dump(),
            "overall_risk": output.overall_risk.value,
            "escalation_state": output.escalation.state.value,
            "requires_human_review": output.requires_human_review
        }, status
