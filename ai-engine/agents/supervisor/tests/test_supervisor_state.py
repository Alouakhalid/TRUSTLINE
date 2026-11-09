"""Unit tests for Supervisor state schemas and Pydantic validation."""
import pytest
from datetime import datetime
from supervisor.schemas.state import SupervisorMultiAgentState
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.schemas.assessment import (
    FinalSupervisorAssessment,
    WorkflowCompletionStatus,
    AgentExecutionState,
    AgentExecutionStatus,
    EvidenceRegistryItem,
    CoverageSummary
)

def test_01_state_initialization_and_serialization():
    """Verify SupervisorMultiAgentState handles typed dictionary keys without errors."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "request_id": "REQ-12345",
        "workflow_id": "WF-9999",
        "workflow_status": "IN_PROGRESS",
        "errors": [],
        "warnings": ["Initial test warning"],
        "missing_data": []
    }
    assert state["astronaut_id"] == "AST-001"
    assert state["workflow_status"] == "IN_PROGRESS"
    assert len(state["warnings"]) == 1

def test_02_request_schema_validation():
    """Verify SupervisorRequest validates required subject IDs and modalities."""
    req = SupervisorRequest(
        request_id="REQ-TEST-1",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Status check post EVA",
            sensor_manifest_path="data/input/astronaut_health_data.json"
        )
    )
    assert req.request_id == "REQ-TEST-1"
    assert req.input_data.text_query == "Status check post EVA"
    assert req.modality == InputModality.MULTIMODAL

def test_03_final_assessment_schema_contracts():
    """Verify FinalSupervisorAssessment validates required fields and enum types."""
    assessment = FinalSupervisorAssessment(
        assessment_id="SUP-001",
        astronaut_id="AST-001",
        session_id="SESSION-001",
        workflow_id="WF-001",
        generation_timestamp=datetime.utcnow(),
        workflow_completion_status=WorkflowCompletionStatus.PARTIALLY_COMPLETED,
        agent_execution_statuses={
            "sensor_quality_agent": AgentExecutionStatus(
                agent_name="sensor_quality_agent",
                status=AgentExecutionState.SUCCESS,
                execution_time_ms=120.5
            )
        },
        overall_assessment_status="PARTIALLY_COMPLETED",
        overall_risk="INSUFFICIENT_DATA",
        overall_confidence="MODERATE",
        escalation_state="NO_TRIGGER_DETECTED",
        escalation_required=False,
        coverage_summary=CoverageSummary(
            total_domains=10,
            evaluated_domains=["CARDIOVASCULAR", "RESPIRATORY"],
            unevaluated_domains=["NEUROLOGICAL"],
            domain_coverage_ratio=0.2,
            coverage_status="PARTIAL"
        ),
        astronaut_facing_response="All systems nominal within monitored parameters."
    )
    assert assessment.assessment_id == "SUP-001"
    assert assessment.workflow_completion_status == WorkflowCompletionStatus.PARTIALLY_COMPLETED
    assert assessment.coverage_summary.domain_coverage_ratio == 0.2
