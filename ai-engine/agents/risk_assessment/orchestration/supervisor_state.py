"""Supervisor multi-agent state representation and workflow orchestrator."""
from typing import Dict, List, Optional, Any, TypedDict
from ..agent.agent import risk_assessment_langgraph_node

class SupervisorMultiAgentState(TypedDict, total=False):
    """Shared state dictionary representing data flowing across the four TRUSTLINE agents."""
    astronaut_id: str
    session_id: str
    workflow_id: str
    current_step: str
    workflow_status: str
    raw_manifest: Optional[Dict[str, Any]]
    sensor_quality_report: Optional[Dict[str, Any]]
    personal_health_assessment: Optional[Dict[str, Any]]
    risk_assessment_output: Optional[Dict[str, Any]]
    confirmed_medical_records: List[Dict[str, Any]]
    mission_context: Optional[Dict[str, Any]]
    overall_risk: Optional[str]
    escalation_state: Optional[str]
    requires_human_review: Optional[bool]
    errors: List[str]
    warnings: List[str]

class SupervisorWorkflowRunner:
    """Orchestrator sequencing Sensor Quality, Personal Health, Risk Assessment, and Supervisor compilation."""

    @classmethod
    def execute_multi_agent_pipeline(cls, initial_state: SupervisorMultiAgentState) -> SupervisorMultiAgentState:
        """Run sequential state machine representing TRUSTLINE multi-agent workflow."""
        state = dict(initial_state)
        state.setdefault("errors", [])
        state.setdefault("warnings", [])
        state["workflow_status"] = "IN_PROGRESS"

        try:
            state["current_step"] = "RISK_ASSESSMENT"
            ra_update = risk_assessment_langgraph_node(state)
            state.update(ra_update)
            state["workflow_status"] = "COMPLETED"
        except Exception as exc:
            state["workflow_status"] = "FAILED"
            state["errors"].append(f"Risk assessment step failed: {str(exc)}")

        return state
