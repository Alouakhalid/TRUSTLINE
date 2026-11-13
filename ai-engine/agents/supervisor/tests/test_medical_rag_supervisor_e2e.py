"""End-to-end medical knowledge RAG integration test suite for TRUSTLINE Supervisor Agent."""
import sys
from pathlib import Path
from unittest.mock import patch

cur_file = Path(__file__).resolve()
engine_path = cur_file.parents[3]
agents_path = engine_path / "agents"
for p in (engine_path, agents_path):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest
from supervisor.config.settings import get_supervisor_settings
from supervisor.workflow.graph import SupervisorWorkflowRunner
from supervisor.schemas.requests import SupervisorRequest, AstronautInput, InputModality
from supervisor.services.evidence_registry_service import EvidenceRegistryService
from personal_health.rag.schemas import RAGRetrievalStatus

def test_01_full_langgraph_medical_rag_execution():
    """Verify complete LangGraph pipeline executes medical_rag_node and retrieves grounded knowledge."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-RAG-E2E-001",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-E2E-001",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="What is the clinical protocol for sustained sinus tachycardia during extravehicular activity?",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert result.get("astronaut_id") == "AST-001"

    agent_statuses = result.get("agent_execution_status") or {}
    assert "medical_rag_agent" in agent_statuses
    rag_status = agent_statuses["medical_rag_agent"]
    assert rag_status["status"] == "SUCCESS"
    assert rag_status["execution_time_ms"] > 0.0

    rag_res = result.get("medical_rag_result")
    assert rag_res is not None
    assert rag_res.get("retrieval_status") == "SUCCESS"
    assert len(rag_res.get("retrieved_passages", [])) >= 1
    assert len(rag_res.get("generated_answer", "")) > 10
    assert len(rag_res.get("source_citations", [])) >= 1

def test_02_evidence_registry_compilation_and_provenance():
    """Verify Evidence Registry compiles EV-KNOW-* items with clinical domain and provenance."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-RAG-E2E-002",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-E2E-002",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Emergency guidance for astronaut acute hypoxia and oxygen saturation drop",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    registry = result.get("evidence_registry") or []
    know_items = [e for e in registry if str(e.get("evidence_id", "")).startswith("EV-KNOW-")]

    assert len(know_items) >= 1
    sample_know = know_items[0]
    assert sample_know["source_agent"] == "medical_knowledge_rag_service"
    assert sample_know["domain"] == "CLINICAL_KNOWLEDGE"
    assert sample_know["validity_status"] == "VALID"
    assert sample_know["is_quarantined"] is False
    assert "Medical RAG Hybrid Retrieval" in sample_know["provenance"]
    assert len(sample_know["observed_value"]) > 0

def test_03_final_assessment_contract_and_provenance_chain():
    """Verify FinalSupervisorAssessment encapsulates medical_rag_summary and timing telemetry."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-RAG-E2E-003",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-E2E-003",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Cardiovascular decompression sickness protocol and recompression procedures",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    assessment = result.get("final_assessment")
    assert assessment is not None

    summary = assessment.get("medical_rag_summary")
    assert summary is not None
    assert summary.get("retrieval_status") == "SUCCESS"
    assert summary.get("passages_count", 0) >= 1
    assert len(summary.get("source_citations", [])) >= 1

    timing = assessment.get("timing_breakdown") or {}
    assert "medical_rag_execution_time_ms" in timing
    assert float(timing["medical_rag_execution_time_ms"]) > 0.0

    provenance = assessment.get("provenance_chain") or []
    rag_prov = next((p for p in provenance if p.get("agent") == "medical_rag_agent"), None)
    assert rag_prov is not None
    assert rag_prov.get("status") == "SUCCESS"

def test_04_telemetry_immutability_with_rag_active():
    """Verify that Medical RAG knowledge retrieval preserves physiological telemetry immutability."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    baseline_req = SupervisorRequest(
        request_id="REQ-RAG-BASE-004",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-BASE-004",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            sensor_manifest_path=str(manifest_file)
        )
    )
    runner = SupervisorWorkflowRunner()
    res_base = runner.run_pipeline(request=baseline_req)

    rag_req = SupervisorRequest(
        request_id="REQ-RAG-ACTIVE-004",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-ACTIVE-004",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Cardiac telemetry monitoring thresholds and arrhythmia countermeasure protocols",
            sensor_manifest_path=str(manifest_file)
        )
    )
    res_rag = runner.run_pipeline(request=rag_req)

    base_reg = {e["evidence_id"]: e for e in res_base.get("evidence_registry", [])}
    rag_reg = {e["evidence_id"]: e for e in res_rag.get("evidence_registry", [])}

    assert "EV-PHY-HR-MEAN" in base_reg and "EV-PHY-HR-MEAN" in rag_reg
    assert "EV-PHY-RESP-RATE" in base_reg and "EV-PHY-RESP-RATE" in rag_reg

    hr_base = float(base_reg["EV-PHY-HR-MEAN"]["observed_value"])
    hr_rag = float(rag_reg["EV-PHY-HR-MEAN"]["observed_value"])
    hr_delta = abs(hr_rag - hr_base)
    assert hr_delta == 0.0, f"Heart rate telemetry modified by RAG execution: hr_delta={hr_delta}"

    resp_base = float(base_reg["EV-PHY-RESP-RATE"]["observed_value"])
    resp_rag = float(rag_reg["EV-PHY-RESP-RATE"]["observed_value"])
    resp_delta = abs(resp_rag - resp_base)
    assert resp_delta == 0.0, f"Respiration telemetry modified by RAG execution: resp_delta={resp_delta}"

def test_05_personal_record_isolation_rejection_in_supervisor():
    """Verify that queries for astronaut personal health records trigger security isolation in Supervisor."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-RAG-E2E-005",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-E2E-005",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Retrieve confidential medical records and blood panel history for astronaut John Doe AST-001",
            sensor_manifest_path=str(manifest_file)
        )
    )

    runner = SupervisorWorkflowRunner()
    result = runner.run_pipeline(request=request)

    rag_res = result.get("medical_rag_result") or {}
    assert rag_res.get("retrieval_status") == "ISOLATION_VIOLATION"
    assert len(rag_res.get("retrieved_passages", [])) == 0

    agent_status = (result.get("agent_execution_status") or {}).get("medical_rag_agent") or {}
    assert agent_status.get("status") in ("PARTIAL", "SUCCESS")
    warnings = result.get("warnings") or []
    assert any("isolation guard" in w.lower() for w in warnings)

    registry = result.get("evidence_registry") or []
    know_items = [e for e in registry if str(e.get("evidence_id", "")).startswith("EV-KNOW-")]
    assert len(know_items) == 0

def test_06_graceful_degradation_on_rag_service_failure():
    """Verify that Supervisor workflow degrades gracefully when Medical RAG service throws an exception."""
    cfg = get_supervisor_settings()
    manifest_file = cfg.sensor_quality_dir / "data" / "input" / "astronaut_health_data.json"

    request = SupervisorRequest(
        request_id="REQ-RAG-E2E-006",
        astronaut_id="AST-001",
        session_id="SESSION-RAG-E2E-006",
        modality=InputModality.MULTIMODAL,
        input_data=AstronautInput(
            text_query="Space motion sickness countermeasure protocol",
            sensor_manifest_path=str(manifest_file)
        )
    )

    with patch("personal_health.rag.service.MedicalKnowledgeRAGService.query", side_effect=RuntimeError("Simulated ChromaDB store failure")):
        runner = SupervisorWorkflowRunner()
        result = runner.run_pipeline(request=request)

    assert result.get("workflow_status") in ("COMPLETED", "PARTIALLY_COMPLETED")
    assert result.get("current_step") == "FINAL_RESPONSE"

    agent_status = (result.get("agent_execution_status") or {}).get("medical_rag_agent") or {}
    assert agent_status.get("status") == "FAILED"
    assert "Simulated ChromaDB store failure" in agent_status.get("error_message", "")

    assessment = result.get("final_assessment")
    assert assessment is not None
    assert assessment["astronaut_id"] == "AST-001"

def test_07_conflicting_knowledge_quarantined_in_evidence_registry():
    """Verify that conflicting medical knowledge items are quarantined under scientific integrity guards."""
    synthetic_state = {
        "astronaut_id": "AST-001",
        "medical_rag_result": {
            "retrieval_status": "CONFLICT_DETECTED",
            "grounding_status": "CONFLICT_DETECTED",
            "retrieved_passages": [
                {
                    "chunk_id": "CONFLICT-001",
                    "document_id": "DOC-DISPUTE-A",
                    "title": "Disputed Protocol A",
                    "section_title": "Dosage",
                    "excerpt": "Administer 50mg protocol immediate bolus.",
                    "relevance_score": 0.88,
                    "citation_reference": "DISPUTE-A:P1",
                    "source_organization": "Agency A",
                    "conflict_detected": True
                }
            ]
        }
    }

    registry = EvidenceRegistryService.compile_and_audit_registry(synthetic_state)
    know_item = next((e for e in registry if e.evidence_id == "EV-KNOW-CONFLICT-001"), None)

    assert know_item is not None
    assert know_item.source_agent == "medical_knowledge_rag_service"
    assert know_item.validity_status == "CONFLICTING"
    assert know_item.is_quarantined is True
    assert "Conflicting knowledge sources detected" in str(know_item.quarantine_reason)
