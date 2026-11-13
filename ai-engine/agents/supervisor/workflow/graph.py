"""LangGraph workflow definition and orchestrator runner for TRUSTLINE Supervisor Agent."""
import uuid
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from ..schemas.state import SupervisorMultiAgentState
from ..schemas.requests import SupervisorRequest
from ..schemas.assessment import FinalSupervisorAssessment
from .nodes import (
    intake_node,
    input_validation_node,
    sensor_quality_node,
    personal_health_node,
    medical_rag_node,
    risk_assessment_node,
    evidence_validation_node,
    final_synthesis_node,
    persistence_node,
    final_response_node
)
from .router import route_after_validation

def create_supervisor_workflow() -> Any:
    """Build and compile the 10-node LangGraph StateGraph orchestrator."""
    graph = StateGraph(SupervisorMultiAgentState)

    graph.add_node("intake", intake_node)
    graph.add_node("input_validation", input_validation_node)
    graph.add_node("sensor_quality", sensor_quality_node)
    graph.add_node("personal_health", personal_health_node)
    graph.add_node("medical_rag", medical_rag_node)
    graph.add_node("risk_assessment", risk_assessment_node)
    graph.add_node("evidence_validation", evidence_validation_node)
    graph.add_node("final_synthesis", final_synthesis_node)
    graph.add_node("persistence", persistence_node)
    graph.add_node("final_response", final_response_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "input_validation")

    graph.add_conditional_edges(
        "input_validation",
        route_after_validation,
        {
            "sensor_quality": "sensor_quality",
            "evidence_validation": "evidence_validation"
        }
    )

    graph.add_edge("sensor_quality", "personal_health")
    graph.add_edge("personal_health", "medical_rag")
    graph.add_edge("medical_rag", "risk_assessment")
    graph.add_edge("risk_assessment", "evidence_validation")
    graph.add_edge("evidence_validation", "final_synthesis")
    graph.add_edge("final_synthesis", "persistence")
    graph.add_edge("persistence", "final_response")
    graph.add_edge("final_response", END)

    return graph.compile()

class SupervisorWorkflowRunner:
    """Orchestrator runner converting external requests into state machine invocations."""

    def __init__(self):
        self.app = create_supervisor_workflow()

    def run_pipeline(
        self,
        request: Optional[SupervisorRequest] = None,
        initial_state: Optional[SupervisorMultiAgentState] = None
    ) -> Dict[str, Any]:
        """Execute end-to-end multi-agent LangGraph workflow and return resulting state."""
        state: SupervisorMultiAgentState = {}

        if initial_state is not None:
            state.update(initial_state)

        if request is not None:
            state["request_id"] = request.request_id
            state["astronaut_id"] = request.astronaut_id
            state["session_id"] = request.session_id
            state["incoming_request"] = request.model_dump()

            inp = request.input_data
            if inp.sensor_manifest_path:
                state["manifest_path"] = inp.sensor_manifest_path
            if inp.raw_sensor_manifest:
                state["sensor_data"] = inp.raw_sensor_manifest
            if inp.text_query:
                state["reported_symptoms_text"] = inp.text_query
            if inp.voice_audio_path:
                state["reported_symptoms_voice_path"] = inp.voice_audio_path
            if inp.voice_language:
                state["voice_language"] = inp.voice_language
            if inp.mission_context:
                state["mission_context"] = inp.mission_context
            if inp.document_paths:
                state["document_paths"] = inp.document_paths

        if not state.get("workflow_id"):
            state["workflow_id"] = f"WF-{uuid.uuid4().hex[:8].upper()}"

        result_state = self.app.invoke(state)
        return result_state
