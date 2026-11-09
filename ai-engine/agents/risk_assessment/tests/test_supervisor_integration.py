"""Unit tests for Risk Assessment integration into Supervisor multi-agent LangGraph workflow."""
import pytest
from datetime import datetime
from risk_assessment.agent.agent import risk_assessment_langgraph_node
from risk_assessment.orchestration.supervisor_state import (
    SupervisorMultiAgentState,
    SupervisorWorkflowRunner
)
from sensor_quality.schemas.output_schema import SensorQualityReport, OverallQuality, ProcessingDecision
from sensor_quality.schemas.signal_schema import QualityStatus
from personal_health.schemas.assessment import (
    PersonalHealthAssessment,
    AssessmentStatus,
    BaselineStatus
)
from personal_health.schemas.physiological_features import Core14Features
from personal_health.schemas.ml_prediction import MLInferenceResult

def _build_test_sqr(astro_id: str = "AST-001", session_id: str = "S-001") -> SensorQualityReport:
    """Build mock SensorQualityReport for multi-agent integration tests."""
    return SensorQualityReport(
        astronaut_id=astro_id,
        session_id=session_id,
        execution_timestamp=datetime.utcnow().isoformat(),
        overall_quality=OverallQuality(
            score=0.96,
            status=QualityStatus.VALID,
            valid_sensors_count=3,
            total_sensors_count=3
        ),
        sensors={},
        processing_decision=ProcessingDecision(can_proceed=True)
    )

def _build_test_pha(astro_id: str = "AST-001", session_id: str = "S-001") -> PersonalHealthAssessment:
    """Build mock PersonalHealthAssessment for multi-agent integration tests."""
    return PersonalHealthAssessment(
        astronaut_id=astro_id,
        session_id=session_id,
        assessment_id="PHA-001",
        execution_timestamp=datetime.utcnow(),
        assessment_status=AssessmentStatus.COMPLETED,
        baseline_status=BaselineStatus.NOT_AVAILABLE,
        core_features=Core14Features(
            hr_mean_bpm=74.0,
            hr_std_bpm=4.0,
            hrv_rmssd_ms=42.0,
            hrv_sdnn_ms=50.0,
            eda_mean=2.1,
            eda_std=0.2,
            eda_iqr=0.3,
            resp_rate_bpm=14.5,
            resp_std=0.5,
            temp_mean=36.7,
            temp_std=0.1,
            emg_rms=0.015,
            acc_magnitude_mean=1.0,
            acc_magnitude_std=0.05
        ),
        ml_findings=[
            MLInferenceResult(
                model_id="M-HGB-01",
                model_name="best_hist_gradient_boosting.pkl",
                version="1.0.0",
                target_definition="WESAD experimental laboratory benchmark",
                stress_probability=0.15,
                verdict="BASELINE"
            )
        ],
        llm_executive_synthesis="Nominal rest state."
    )

def test_01_langgraph_node_state_transformation():
    """Verify risk_assessment_langgraph_node consumes supervisor state and updates required keys."""
    sqr = _build_test_sqr()
    pha = _build_test_pha()

    input_state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "S-001",
        "workflow_id": "WF-001",
        "current_step": "PERSONAL_HEALTH",
        "sensor_quality_report": sqr.model_dump(),
        "personal_health_assessment": pha.model_dump(),
        "confirmed_medical_records": [],
        "mission_context": {
            "mission_id": "ARES-1",
            "crew_id": "CREW-A",
            "phase": "CRUISE",
            "day_in_mission": 12,
            "mission_elapsed_time_hours": 288.0
        }
    }

    result = risk_assessment_langgraph_node(input_state)

    assert "risk_assessment_output" in result
    assert "overall_risk" in result
    assert "escalation_state" in result
    assert "requires_human_review" in result
    assert result["current_step"] == "SUPERVISOR_COMPILATION"
    assert result["overall_risk"] in ("LOW", "MODERATE", "HIGH", "CRITICAL", "INSUFFICIENT_DATA", "UNKNOWN")

def test_02_supervisor_workflow_runner_end_to_end():
    """Verify SupervisorWorkflowRunner executes pipeline step, transitioning to COMPLETED."""
    sqr = _build_test_sqr()
    pha = _build_test_pha()

    initial_state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "S-001",
        "workflow_id": "WF-100",
        "sensor_quality_report": sqr.model_dump(),
        "personal_health_assessment": pha.model_dump(),
        "confirmed_medical_records": []
    }

    final_state = SupervisorWorkflowRunner.execute_multi_agent_pipeline(initial_state)

    assert final_state["workflow_status"] == "COMPLETED"
    assert final_state["current_step"] == "SUPERVISOR_COMPILATION"
    assert "risk_assessment_output" in final_state
    assert len(final_state["errors"]) == 0

def test_03_handling_missing_upstream_telemetry():
    """Verify graceful handling when upstream sensor quality and personal health are omitted."""
    sparse_state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-SPARSE",
        "session_id": "S-SPARSE",
        "workflow_id": "WF-200"
    }

    result = risk_assessment_langgraph_node(sparse_state)

    assert result["current_step"] == "SUPERVISOR_COMPILATION"
    output = result["risk_assessment_output"]
    assert output["astronaut_id"] == "AST-SPARSE"
    assert output["assessment_status"] in ("PARTIALLY_COMPLETED", "INSUFFICIENT_DATA")
    assert result["domain_coverage_ratio"] < 1.0

def test_04_error_propagation_on_invalid_astronaut_id():
    """Verify validation failure inside node produces PROCESSING_FAILED status without unhandled exceptions."""
    invalid_state: SupervisorMultiAgentState = {
        "astronaut_id": "",
        "session_id": "S-ERR",
        "workflow_id": "WF-300"
    }

    result = risk_assessment_langgraph_node(invalid_state)

    output = result["risk_assessment_output"]
    assert output["assessment_status"] == "PROCESSING_FAILED"
    assert result["escalation_state"] == "ASSESSMENT_FAILED"
    assert result["requires_human_review"] is True
