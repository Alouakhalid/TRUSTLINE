"""End-to-end integration test executing the complete 4-agent LangGraph workflow."""
import pytest
from pathlib import Path
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.config.settings import get_supervisor_settings

def test_01_four_agent_end_to_end_integration_live(tmp_path):
    """Execute complete 4-agent LangGraph workflow with real agent implementations and biosensor fixture."""
    cfg = get_supervisor_settings()
    orig = cfg.output_dir
    try:
        cfg.output_dir = tmp_path

        manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"
        assert manifest_file.exists(), f"Required test fixture missing: {manifest_file}"

        request = SupervisorRequest(
            request_id="REQ-E2E-TEST-001",
            astronaut_id="AST-001",
            session_id="SESSION-001",
            modality=InputModality.MULTIMODAL,
            input_data=AstronautInput(
                text_query="Routine physiological telemetry assessment post EV-activity.",
                sensor_manifest_path=str(manifest_file),
                mission_context={
                    "mission_id": "ARES-1",
                    "crew_id": "CREW-A",
                    "phase": "CRUISE",
                    "day_in_mission": 14,
                    "mission_elapsed_time_hours": 336.0
                }
            )
        )

        runner = SupervisorWorkflowRunner()
        result_state = runner.run_pipeline(request=request)

        assert result_state.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
        assert result_state.get("astronaut_id") == "AST-001"
        assert result_state.get("session_id") == "SESSION-001"
        assert result_state.get("overall_risk") == "INSUFFICIENT_DATA"
        assert result_state.get("escalation_state") == "NO_TRIGGER_DETECTED"

        agent_statuses = result_state.get("agent_execution_status") or {}
        assert "sensor_quality_agent" in agent_statuses
        assert "personal_health_agent" in agent_statuses
        assert "risk_assessment_agent" in agent_statuses

        sq_st = agent_statuses["sensor_quality_agent"]
        assert sq_st.get("status") in ("SUCCESS", "PARTIAL")

        pha_st = agent_statuses["personal_health_agent"]
        assert pha_st.get("status") in ("SUCCESS", "PARTIAL")

        ra_st = agent_statuses["risk_assessment_agent"]
        assert ra_st.get("status") == "SUCCESS"

        final_assessment = result_state.get("final_assessment")
        assert final_assessment is not None
        assert final_assessment["overall_risk"] == "INSUFFICIENT_DATA"
        assert final_assessment["coverage_summary"]["domain_coverage_ratio"] in (0.5, 0.6)
        assert len(final_assessment["coverage_summary"]["evaluated_domains"]) in (5, 6)
        assert len(final_assessment["coverage_summary"]["unevaluated_domains"]) in (4, 5)

        registry = result_state.get("evidence_registry")
        assert registry is not None
        hrv_item = next((item for item in registry if item["evidence_id"] == "EV-PHY-HRV-RMSSD"), None)
        assert hrv_item is not None
        assert hrv_item["is_quarantined"] is True
        assert hrv_item["validity_status"] == "INVALID"

        resp = result_state.get("final_response")
        assert resp is not None
        assert "TRUSTLINE Mission Health Briefing" in resp
        assert "AST-001" in resp
        assert "SESSION-001" in resp
        assert "ACT-NOM-001" in resp

        out_file = tmp_path / "final_supervisor_assessment.json"
        assert out_file.exists()
    finally:
        cfg.output_dir = orig
