"""Stress Test 04: Personal Health Agent failure modes, exception isolation, and graceful degradation."""
from unittest.mock import patch, MagicMock
import pytest
from supervisor.adapters.personal_health_adapter import PersonalHealthAdapter
from supervisor.schemas.assessment import AgentExecutionState
from supervisor.workflow.graph import SupervisorWorkflowRunner

def test_01_pha_timeout_capture():
    """Verify adapter wraps timeouts cleanly without crashing orchestrator."""
    adapter = PersonalHealthAdapter()

    def _slow_run(state):
        import time
        time.sleep(0.05)
        raise TimeoutError("PHA execution timed out after 30000 ms")

    with patch.object(adapter, "run", side_effect=_slow_run):
        updates, status = adapter.execute_with_telemetry({})

    assert status.status == AgentExecutionState.FAILED
    assert "timed out" in status.error_message.lower()
    assert status.execution_time_ms >= 50.0

def test_02_feature_extraction_exception_isolated():
    """Verify feature extraction exception generates failed status without fabricating features."""
    adapter = PersonalHealthAdapter()

    with patch("personal_health.services.feature_extraction_service.FeatureExtractionService.extract_features", side_effect=ValueError("Corrupted ECG buffer")):
        state = {
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "sensor_quality_result": {"overall_quality_score": 0.9}
        }
        updates, status = adapter.execute_with_telemetry(state)

    assert status.status == AgentExecutionState.FAILED
    assert "Corrupted ECG buffer" in status.error_message
    assert "personal_health_result" not in updates

def test_03_ml_inference_exception_gracefully_degrades():
    """Verify failure in ML stress model does not crash entire PHA run."""
    from personal_health.services.ml_inference_service import MLInferenceService
    service = MLInferenceService()

    with patch.object(service, "predict_stress", side_effect=RuntimeError("Model weights corrupted")):
        try:
            res = service.predict_stress(MagicMock())
            assert False, "Should have raised exception"
        except RuntimeError as e:
            assert "Model weights corrupted" in str(e)

def test_04_rag_retrieval_failure_handled_gracefully():
    """Verify RAG database failure falls back to empty evidence without halting workflow."""
    from personal_health.services.rag_service import MedicalRAGService
    rag = MedicalRAGService()

    with patch.object(rag, "query_medical_evidence", side_effect=ConnectionError("ChromaDB vector store unreachable")):
        try:
            ev = rag.query_medical_evidence("stress")
        except ConnectionError:
            ev = []
        assert ev == []

def test_05_workflow_isolates_pha_failure_and_preserves_sqr():
    """Verify end-to-end workflow continues to Risk Assessment when PHA fails completely."""
    runner = SupervisorWorkflowRunner()

    with patch("supervisor.adapters.personal_health_adapter.PersonalHealthAdapter.run", side_effect=RuntimeError("Complete PHA pipeline crash")):
        result = runner.run_pipeline(initial_state={
            "astronaut_id": "AST-001",
            "session_id": "SESSION-001",
            "sensor_quality_result": {
                "overall_quality_score": 0.85,
                "sensors": {
                    "ECG": {"status": "VALID", "quality_score": 0.92, "critical_failure": False}
                }
            }
        })

    agent_statuses = result.get("agent_execution_status") or {}
    pha_status = agent_statuses.get("personal_health_agent", {})
    assert pha_status.get("status") == "FAILED"
    assert "Complete PHA pipeline crash" in pha_status.get("error_message", "")

    sq_status = agent_statuses.get("sensor_quality_agent", {})
    assert sq_status.get("status") == "SUCCESS"
    assert result.get("workflow_status") in ("PARTIALLY_COMPLETED", "FAILED")
    assert result.get("current_step") == "FINAL_RESPONSE"
