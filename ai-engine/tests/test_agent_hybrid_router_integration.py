"""
TRUSTLINE Priority 04: Agent Hybrid AI Router Integration Test Suite.
Tests the 9 required failure, recovery, capability, grounding, and AST integration scenarios.
"""
import ast
import os
import json
import pytest
from unittest.mock import MagicMock, patch

from hybrid_ai import (
    HybridAIRouter,
    GroqProvider,
    OllamaProvider,
    CircuitBreaker,
    ProviderRequest,
    ProviderResponse,
    TaskCategory,
    RoutingPolicy,
    ProviderType,
    CircuitState,
    TaskNotEligibleError,
    ProviderUnavailableError,
    ProviderAuthenticationError,
    CapabilityRegistry
)

from risk_assessment.services.llm_interpretation_service import LLMInterpretationService
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState
from risk_assessment.services.claim_grounding_validator import ClaimGroundingValidator
from personal_health.rag.generation import GroundedMedicalGenerator
from personal_health.rag.schemas import RetrievedPassage, RAGRetrievalStatus
from personal_health.services.symptom_service import SymptomService
from personal_health.schemas.symptom_event import InputChannel, SymptomCategory, SymptomSeverity
from personal_health.agent.agent import generate_clinical_synthesis
from sensor_quality_agent.agent.agent import generate_llm_briefing

@pytest.fixture
def mock_router():
    """Create a mock router allowing configurable responses."""
    router = MagicMock(spec=HybridAIRouter)
    router.mode = "HYBRID"
    return router

# -----------------------------------------------------------------------------
# 1. Normal Groq execution through the router for each agent service
# -----------------------------------------------------------------------------
def test_01_normal_groq_execution_through_router(mock_router):
    """Verify each agent service delegates to HybridAIRouter under normal cloud operation."""
    # LLMInterpretationService
    mock_router.route_request.return_value = ProviderResponse(
        request_id="REQ-TEST-01",
        provider=ProviderType.GROQ,
        model="qwen/qwen3.8-27b",
        content="Telemetry indicates moderate tachycardia. No acute red-line triggers identified. Continued monitoring advised.",
        latency_ms=120.0,
        is_fallback=False,
        success=True
    )
    svc = LLMInterpretationService(api_key="gsk-test", router=mock_router)
    text, status = svc.generate_explanation(
        astronaut_id="AST-001",
        session_id="SES-001",
        overall_risk=RiskLevel.MODERATE,
        overall_confidence="HIGH",
        escalation_state=EscalationState.REVIEW_REQUIRED,
        escalation_reason="Moderate tachycardia",
        domain_summaries=[],
        concerns=[{"title": "Moderate Tachycardia"}],
        protective_factors=[],
        uncertainties=[]
    )
    assert status == "LLM_SUCCESS"
    assert "tachycardia" in text
    assert mock_router.route_request.called
    assert mock_router.route_request.call_args[0][0].task_category == TaskCategory.RISK_ASSESSMENT_SYNTHESIS

    # MedicalRAGGenerator
    mock_router.reset_mock()
    mock_router.route_request.return_value = ProviderResponse(
        request_id="REQ-TEST-01B",
        provider=ProviderType.GROQ,
        model="qwen/qwen3.8-27b",
        content="**1. Retrieved Medical Facts:** NASA guideline requires 100 bpm baseline check.\n\n**2. Clinical Interpretation:** Normal.\n\n**3. Uncertainty & Limitations:** None.\n\n**4. Source Citations:** [NASA-01:P1]\n\n**5. Missing Information:** Baseline data.",
        latency_ms=150.0,
        is_fallback=False,
        success=True
    )
    rag_gen = GroundedMedicalGenerator(api_key="gsk-test", router=mock_router)
    passage = RetrievedPassage(
        chunk_id="C1",
        document_id="D1",
        title="Guideline",
        source_organization="NASA",
        excerpt="NASA guideline requires 100 bpm baseline check.",
        relevance_score=0.9,
        citation_reference="NASA-01:P1"
    )
    res = rag_gen.generate(query="Heart rate", passages=[passage], retrieval_status=RAGRetrievalStatus.SUCCESS)
    assert mock_router.route_request.called
    assert mock_router.route_request.call_args[0][0].task_category == TaskCategory.MEDICAL_RAG_SYNTHESIS
    assert "NASA guideline" in res.generated_answer

# -----------------------------------------------------------------------------
# 2. Cloud authentication failure followed by local fallback for an eligible task
# -----------------------------------------------------------------------------
def test_02_cloud_auth_failure_triggers_local_fallback_for_eligible_task():
    """Verify router catches ProviderAuthenticationError and falls back to Ollama."""
    mock_groq = MagicMock(spec=GroqProvider)
    mock_groq.generate.side_effect = ProviderAuthenticationError("401 Invalid API Key")
    mock_ollama = MagicMock(spec=OllamaProvider)
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-FALLBACK",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Grounded fallback interpretation from edge model.",
        latency_ms=3500.0,
        tokens_per_second=12.5,
        is_fallback=True,
        success=True
    )
    cb = CircuitBreaker(failure_threshold=3)
    router = HybridAIRouter(groq_provider=mock_groq, ollama_provider=mock_ollama, circuit_breaker=cb)

    req = ProviderRequest(
        task_category=TaskCategory.RISK_ASSESSMENT_SYNTHESIS,
        prompt="Assess astronaut risk",
        system_prompt="Clinical system prompt"
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert resp.is_fallback is True
    assert "ProviderAuthenticationError" in resp.fallback_reason
    assert mock_groq.generate.called
    assert mock_ollama.generate.called

# -----------------------------------------------------------------------------
# 3. Local provider failure followed by deterministic safe fallback
# -----------------------------------------------------------------------------
def test_03_local_provider_failure_cleanly_defaults_to_deterministic_fallback():
    """When both cloud and local providers fail, services cleanly drop to deterministic fallback."""
    failing_router = MagicMock(spec=HybridAIRouter)
    failing_router.mode = "HYBRID"
    failing_router.route_request.side_effect = ProviderUnavailableError("Both cloud and local unavailable")

    # LLMInterpretationService
    svc = LLMInterpretationService(api_key="gsk-test", router=failing_router)
    text, status = svc.generate_explanation(
        astronaut_id="AST-001",
        session_id="SES-001",
        overall_risk=RiskLevel.LOW,
        overall_confidence="HIGH",
        escalation_state=EscalationState.NO_TRIGGER_DETECTED,
        escalation_reason="Nominal vitals",
        domain_summaries=[],
        concerns=[],
        protective_factors=[],
        uncertainties=[]
    )
    assert status in ("LLM_UNAVAILABLE", "LLM_UNEXPECTED_ERROR")
    assert len(text.split("\n\n")) == 3
    assert "AST-001" in text

    # MedicalRAGGenerator
    rag_gen = GroundedMedicalGenerator(api_key="gsk-test", router=failing_router)
    passage = RetrievedPassage(
        chunk_id="C1", document_id="D1", title="NASA Protocol",
        source_organization="NASA", excerpt="Guideline excerpt",
        relevance_score=0.9, citation_reference="NASA-01:P1"
    )
    res = rag_gen.generate(query="query", passages=[passage], retrieval_status=RAGRetrievalStatus.SUCCESS)
    assert "**1. Retrieved Medical Facts:**" in res.generated_answer
    assert "**4. Source Citations:**" in res.generated_answer

    # SymptomService
    symptom_svc = SymptomService(router=failing_router)
    event, clar = symptom_svc.process_text_symptom(
        text="Severe chest pain for 30 minutes",
        astronaut_id="AST-001",
        session_id="SES-001"
    )
    assert event is not None
    assert event.symptom_category == SymptomCategory.CARDIORESPIRATORY
    assert event.severity in (SymptomSeverity.SEVERE, SymptomSeverity.CRITICAL)

# -----------------------------------------------------------------------------
# 4. CLOUD_ONLY tasks do not invoke Ollama
# -----------------------------------------------------------------------------
def test_04_cloud_only_tasks_strictly_reject_local_fallback():
    """Verify CLOUD_ONLY tasks raise TaskNotEligibleError and never invoke local Ollama."""
    mock_groq = MagicMock(spec=GroqProvider)
    mock_groq.generate.side_effect = ProviderUnavailableError("Groq 503")
    mock_ollama = MagicMock(spec=OllamaProvider)
    router = HybridAIRouter(groq_provider=mock_groq, ollama_provider=mock_ollama)

    # DOCUMENT_OCR is CLOUD_ONLY
    assert CapabilityRegistry.is_cloud_only(TaskCategory.MEDICAL_DOCUMENT_OCR)
    req_ocr = ProviderRequest(
        task_category=TaskCategory.MEDICAL_DOCUMENT_OCR,
        prompt="Extract document text"
    )
    with pytest.raises(TaskNotEligibleError) as exc_ocr:
        router.route_request(req_ocr)
    assert "cannot fallback to local inference" in str(exc_ocr.value)
    assert not mock_ollama.generate.called

    # VOICE_INTERPRETATION is CLOUD_ONLY
    assert CapabilityRegistry.is_cloud_only(TaskCategory.VOICE_INTERPRETATION)
    req_voice = ProviderRequest(
        task_category=TaskCategory.VOICE_INTERPRETATION,
        prompt="Transcribe audio"
    )
    with pytest.raises(TaskNotEligibleError) as exc_voice:
        router.route_request(req_voice)
    assert "cannot fallback to local inference" in str(exc_voice.value)
    assert not mock_ollama.generate.called

# -----------------------------------------------------------------------------
# 5. Recovery to Groq after cloud credentials become valid
# -----------------------------------------------------------------------------
def test_05_circuit_breaker_recovery_to_groq():
    """Verify circuit breaker transitions OPEN -> HALF_OPEN -> CLOSED and restores Groq routing."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1, half_open_success_threshold=2)
    cb.force_state(CircuitState.OPEN)
    assert cb.state == CircuitState.OPEN

    # Wait for recovery timeout
    import time
    time.sleep(0.15)

    # Next check enters HALF_OPEN
    assert cb.can_attempt_cloud() is True
    assert cb.state == CircuitState.HALF_OPEN

    # First canary success: remains HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.consecutive_successes == 1

    # Second canary success: restores CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_successes == 0
    assert cb.can_attempt_cloud() is True

# -----------------------------------------------------------------------------
# 6. Medical RAG citations and provenance remain valid after local fallback
# -----------------------------------------------------------------------------
def test_06_medical_rag_citations_and_provenance_preserved_after_local_fallback():
    """Verify local fallback output preserves ground-truth citations without hallucination."""
    local_router = MagicMock(spec=HybridAIRouter)
    local_router.mode = "HYBRID"
    local_router.route_request.return_value = ProviderResponse(
        request_id="REQ-RAG-FALLBACK",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content=(
            "**1. Retrieved Medical Facts:** NASA-STD-3001 specifies resting heart rate limits.\n\n"
            "**2. Clinical Interpretation:** Value within operational limits.\n\n"
            "**3. Uncertainty & Limitations:** Grounded in single source.\n\n"
            "**4. Source Citations:** [NASA-STD-3001:P12]\n\n"
            "**5. Missing Information:** Baseline telemetry."
        ),
        is_fallback=True,
        success=True
    )
    generator = GroundedMedicalGenerator(api_key="gsk-key", router=local_router)
    passages = [
        RetrievedPassage(
            chunk_id="CHK-001",
            document_id="DOC-NASA-001",
            title="NASA Space Flight Human-System Standard",
            source_organization="NASA",
            excerpt="NASA-STD-3001 specifies resting heart rate limits for long-duration crew members.",
            relevance_score=0.95,
            citation_reference="NASA-STD-3001:P12"
        )
    ]
    res = generator.generate(query="heart rate limits", passages=passages, retrieval_status=RAGRetrievalStatus.SUCCESS)
    assert res.retrieval_status == RAGRetrievalStatus.SUCCESS
    assert "NASA-STD-3001:P12" in res.source_citations

# -----------------------------------------------------------------------------
# 7. Risk classification cannot be changed by unsupported LLM output
# -----------------------------------------------------------------------------
def test_07_risk_classification_immutable_by_unsupported_llm_output():
    """Verify LLM cannot contradict deterministic rule-engine risk classification."""
    hallucinated_text = "The astronaut is at LOW risk and perfectly normal."
    is_valid, violations = ClaimGroundingValidator.validate_synthesis(
        text=hallucinated_text,
        overall_risk=RiskLevel.CRITICAL,
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        mission_day_supplied=False
    )
    assert is_valid is False
    assert any("contradicts" in v for v in violations)

# -----------------------------------------------------------------------------
# 8. Missing evidence remains UNKNOWN or INSUFFICIENT_DATA
# -----------------------------------------------------------------------------
def test_08_missing_evidence_remains_unknown_or_insufficient_data():
    """Verify missing telemetry or failed agent execution does not default to LOW risk."""
    from supervisor.workflow.graph import SupervisorWorkflowRunner
    from supervisor.schemas.requests import SupervisorRequest, AstronautInput

    runner = SupervisorWorkflowRunner()
    req = SupervisorRequest(
        request_id="REQ-STRESS-MISSING",
        astronaut_id="AST-999",
        session_id="SES-999",
        input_data=AstronautInput(text_query="Status")
    )
    with patch("supervisor.adapters.risk_assessment_adapter.RiskAssessmentAdapter.run", side_effect=RuntimeError("Rule engine crash")):
        result = runner.run_pipeline(req)

    fa = result.get("final_assessment") or {}
    assert fa.get("overall_risk") == "UNKNOWN"
    assert fa.get("escalation_state") == "ASSESSMENT_UNAVAILABLE"
    assert "Clinical risk status is UNKNOWN" in (result.get("final_response") or "")

# -----------------------------------------------------------------------------
# 9. Static AST audit proving zero direct eligible text-generation Groq calls bypass the router
# -----------------------------------------------------------------------------
def test_09_static_ast_audit_no_direct_text_groq_bypasses_router():
    """AST inspection verifying no direct Groq text completion calls remain in agent services."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    target_files = [
        os.path.join(repo_root, "agents/risk_assessment/services/llm_interpretation_service.py"),
        os.path.join(repo_root, "agents/personal_health/rag/generation.py"),
        os.path.join(repo_root, "agents/personal_health/services/symptom_service.py"),
        os.path.join(repo_root, "agents/personal_health/agent/agent.py"),
        os.path.join(repo_root, "agents/sensor_quality/agent/agent.py"),
    ]

    for filepath in target_files:
        assert os.path.exists(filepath), f"File not found: {filepath}"
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)

        # Check for direct calls to chat.completions.create
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "create":
                    if isinstance(func.value, ast.Attribute) and func.value.attr == "completions":
                        # In agent services, text completion MUST go through router.route_request
                        pytest.fail(f"Found unrouted chat.completions.create in {filepath} at line {node.lineno}")
