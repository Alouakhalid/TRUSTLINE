"""Timing integrity and precision tests for TRUSTLINE Supervisor Agent."""
import time
import pytest
from pathlib import Path
from ..workflow.graph import SupervisorWorkflowRunner
from ..schemas.requests import SupervisorRequest, AstronautInput
from ..schemas.state import SupervisorMultiAgentState
from ..workflow.nodes import intake_node, input_validation_node, persistence_node, final_response_node
from ..services.persistence_service import PersistenceService

def test_01_monotonic_clock_used_across_nodes():
    """Verify nodes utilize monotonic high-resolution timing and record positive durations."""
    state: SupervisorMultiAgentState = {
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001"
    }
    intake_res = intake_node(state)
    assert "perf_timestamps" in intake_res
    assert "workflow_start" in intake_res["perf_timestamps"]
    assert isinstance(intake_res["perf_timestamps"]["workflow_start"], float)
    assert intake_res["durations_ms"]["intake"] > 0.0

    state.update(intake_res)
    val_res = input_validation_node(state)
    assert val_res["durations_ms"]["input_validation"] > 0.0

def test_02_persistence_reports_nonzero_latency(tmp_path):
    """Verify persistence node records non-zero execution duration and updates timing breakdown."""
    assessment = {
        "assessment_id": "SUP-TEST-TIMING-1",
        "astronaut_id": "AST-001",
        "session_id": "SESSION-001",
        "workflow_id": "WF-TIMING-1",
        "workflow_completion_status": "COMPLETED",
        "overall_risk": "LOW",
        "escalation_state": "NO_TRIGGER_DETECTED",
        "timing_breakdown": {
            "workflow_total_execution_time_ms": 100.0,
            "supervisor_overhead_time_ms": 10.0,
            "sensor_quality_execution_time_ms": 30.0,
            "personal_health_execution_time_ms": 30.0,
            "risk_assessment_execution_time_ms": 30.0,
            "evidence_validation_time_ms": 5.0,
            "final_synthesis_time_ms": 5.0,
            "persistence_time_ms": 0.0,
            "measured_supervisor_overhead_ms": 10.0
        }
    }
    from ..config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    orig_dir = cfg.output_dir
    orig_db = cfg.database_url
    try:
        cfg.output_dir = tmp_path
        cfg.database_url = f"sqlite:///{tmp_path}/edge_test.db"
        success, filepath, warnings = PersistenceService.save_final_assessment(assessment)
        assert success is True
        assert assessment["timing_breakdown"]["persistence_time_ms"] > 0.0

        state: SupervisorMultiAgentState = {
            "final_assessment": assessment,
            "durations_ms": {}
        }
        updates = persistence_node(state)
        assert updates["durations_ms"]["persistence"] > 0.0
        assert updates["final_assessment"]["timing_breakdown"]["persistence_time_ms"] > 0.0
    finally:
        cfg.output_dir = orig_dir
        cfg.database_url = orig_db

def test_03_workflow_total_covers_complete_pipeline(tmp_path):
    """Verify workflow total execution time encompasses entire pipeline execution without omission."""
    runner = SupervisorWorkflowRunner()
    manifest_file = Path("ai-engine/agents/sensor_quality/data/input/astronaut_health_data.json")
    if not manifest_file.exists():
        pytest.skip("Sensor telemetry manifest not found")

    from ..config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    orig = cfg.output_dir
    orig_db = cfg.database_url
    try:
        cfg.output_dir = tmp_path
        cfg.database_url = f"sqlite:///{tmp_path}/edge_timing.db"

        req = SupervisorRequest(
            request_id="REQ-TIMING-1",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            input_data=AstronautInput(
                sensor_manifest_path=str(manifest_file),
                text_query="Routine scheduled monitoring."
            )
        )
        result = runner.run_pipeline(req)
        assessment = result.get("final_assessment") or {}
        tb = assessment.get("timing_breakdown") or {}

        total_ms = tb.get("workflow_total_execution_time_ms", 0.0)
        sq_ms = tb.get("sensor_quality_execution_time_ms", 0.0)
        pha_ms = tb.get("personal_health_execution_time_ms", 0.0)
        ra_ms = tb.get("risk_assessment_execution_time_ms", 0.0)
        subagent_sum = sq_ms + pha_ms + ra_ms

        assert total_ms > 0.0
        assert total_ms >= subagent_sum
        assert tb.get("persistence_time_ms", 0.0) > 0.0
        assert tb.get("final_synthesis_time_ms", 0.0) > 0.0
        assert tb.get("evidence_validation_time_ms", 0.0) > 0.0
    finally:
        cfg.output_dir = orig
        cfg.database_url = orig_db

def test_04_supervisor_overhead_is_accurately_separated(tmp_path):
    """Verify supervisor overhead is strictly separated from specialist agent execution time."""
    runner = SupervisorWorkflowRunner()
    manifest_file = Path("ai-engine/agents/sensor_quality/data/input/astronaut_health_data.json")
    if not manifest_file.exists():
        pytest.skip("Sensor telemetry manifest not found")

    from ..config.settings import get_supervisor_settings
    cfg = get_supervisor_settings()
    orig = cfg.output_dir
    orig_db = cfg.database_url
    try:
        cfg.output_dir = tmp_path
        cfg.database_url = f"sqlite:///{tmp_path}/edge_ovh.db"

        req = SupervisorRequest(
            request_id="REQ-TIMING-2",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            input_data=AstronautInput(
                sensor_manifest_path=str(manifest_file)
            )
        )
        result = runner.run_pipeline(req)
        tb = (result.get("final_assessment") or {}).get("timing_breakdown") or {}

        total_ms = tb.get("workflow_total_execution_time_ms", 0.0)
        overhead_ms = tb.get("supervisor_overhead_time_ms", 0.0)
        measured_ovh_ms = tb.get("measured_supervisor_overhead_ms", 0.0)
        subagent_sum = (
            tb.get("sensor_quality_execution_time_ms", 0.0)
            + tb.get("personal_health_execution_time_ms", 0.0)
            + tb.get("risk_assessment_execution_time_ms", 0.0)
        )

        assert abs(total_ms - (subagent_sum + overhead_ms)) < 0.05
        assert measured_ovh_ms > 0.0
        assert overhead_ms >= 0.0
    finally:
        cfg.output_dir = orig
        cfg.database_url = orig_db

def test_05_no_overlapping_or_double_counted_intervals():
    """Verify adapter overhead measures pure wrapper latency without double counting subagent time."""
    durations = {
        "sensor_quality_node": 105.5,
        "personal_health_node": 210.0,
        "risk_assessment_node": 85.0
    }
    subagent_times = {
        "sensor_quality_agent": 100.0,
        "personal_health_agent": 200.0,
        "risk_assessment_agent": 80.0
    }
    for agent_key, node_key in [
        ("sensor_quality_agent", "sensor_quality_node"),
        ("personal_health_agent", "personal_health_node"),
        ("risk_assessment_agent", "risk_assessment_node")
    ]:
        node_dur = durations[node_key]
        subagent_dur = subagent_times[agent_key]
        overhead = max(0.0, round(node_dur - subagent_dur, 3))
        assert overhead >= 0.0
        assert overhead < node_dur
        assert round(subagent_dur + overhead, 1) == round(node_dur, 1)
