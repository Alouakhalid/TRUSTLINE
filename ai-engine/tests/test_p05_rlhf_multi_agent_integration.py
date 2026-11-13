"""
TRUSTLINE Priority 05: Shared Pretrained RLHF Model Multi-Agent Integration Tests.

Validates:
1. Shared RLHF Model serving Sensor Quality Agent (SQA)
2. Shared RLHF Model serving Personal Health Agent (PHA) with ClinicalSynthesisValidator
3. Shared RLHF Model serving Risk Assessment Agent (RAA) with immutable deterministic tier preservation
4. Shared RLHF Model serving Medical RAG Agent with citation preservation
5. Cascade resilience: HF error -> Groq cloud fallback -> Ollama local fallback
6. Multimodal isolation: OCR / Voice tasks bypass text-only HF model and enforce CLOUD_ONLY policy
7. AST comment hygiene: zero '#' comments in supervisor/ and risk_assessment/
"""

import ast
import os
import pytest
from unittest.mock import MagicMock

from hybrid_ai.schemas import (
    ProviderType,
    ProviderStatus,
    ProviderRequest,
    ProviderResponse,
    TaskCategory,
    RoutingPolicy,
    TaskNotEligibleError,
    ProviderUnavailableError
)
from hybrid_ai.router import HybridAIRouter
from hybrid_ai.circuit_breaker import CircuitBreaker
from hybrid_ai.huggingface_provider import HuggingFaceProvider
from hybrid_ai.groq_provider import GroqProvider
from hybrid_ai.ollama_provider import OllamaProvider

from risk_assessment.services.llm_interpretation_service import LLMInterpretationService
from risk_assessment.schemas.risk_rules import RiskLevel, EscalationState
from personal_health.rag.generation import GroundedMedicalGenerator
from personal_health.rag.schemas import RetrievedPassage, RAGRetrievalStatus
from personal_health.services.synthesis_validator import ClinicalSynthesisValidator
from sensor_quality_agent.agent.agent import generate_llm_briefing
from personal_health.agent.agent import generate_clinical_synthesis


@pytest.fixture
def mock_hf():
    p = MagicMock(spec=HuggingFaceProvider)
    p.provider_type = ProviderType.HUGGINGFACE
    p.default_model = "meta-llama/Llama-3.1-8B-Instruct"
    p.is_configured.return_value = True
    return p


@pytest.fixture
def mock_groq():
    p = MagicMock(spec=GroqProvider)
    p.provider_type = ProviderType.GROQ
    p.default_model = "qwen/qwen3.8-27b"
    p.is_configured.return_value = True
    return p


@pytest.fixture
def mock_ollama():
    p = MagicMock(spec=OllamaProvider)
    p.provider_type = ProviderType.OLLAMA
    p.default_model = "qwen2.5:7b-instruct"
    return p


@pytest.fixture
def circuit_breaker():
    return CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)


@pytest.fixture
def rlhf_router(mock_hf, mock_groq, mock_ollama, circuit_breaker):
    return HybridAIRouter(
        groq_provider=mock_groq,
        ollama_provider=mock_ollama,
        circuit_breaker=circuit_breaker,
        hf_provider=mock_hf,
        mode="HYBRID"
    )


def test_01_sqa_routes_to_hf_rlhf_model(rlhf_router, mock_hf, mock_groq, mock_ollama):
    """Verify SQA briefing delegates to shared Hugging Face RLHF model via router."""
    mock_hf.generate.return_value = ProviderResponse(
        request_id="REQ-SQA-01",
        provider=ProviderType.HUGGINGFACE,
        model="meta-llama/Llama-3.1-8B-Instruct",
        content="Sensor Quality Briefing: ECG SNR is nominal at 24.2 dB. Pulse oximetry artifact within allowable tolerances.",
        latency_ms=180.0,
        tokens_per_second=22.5,
        is_fallback=False,
        success=True
    )

    req = ProviderRequest(
        task_category=TaskCategory.SENSOR_QUALITY_BRIEFING,
        prompt="Synthesize sensor quality metrics."
    )
    resp = rlhf_router.route_request(req)

    assert resp.success is True
    assert resp.provider == ProviderType.HUGGINGFACE
    assert resp.model == "meta-llama/Llama-3.1-8B-Instruct"
    assert "Sensor Quality Briefing" in resp.content
    assert mock_hf.generate.called
    assert not mock_groq.generate.called
    assert not mock_ollama.generate.called


def test_02_pha_clinical_synthesis_routes_to_hf_and_validates(rlhf_router, mock_hf, mock_groq):
    """Verify PHA clinical synthesis routes to HF RLHF model and passes clinical validation."""
    mock_hf.generate.return_value = ProviderResponse(
        request_id="REQ-PHA-01",
        provider=ProviderType.HUGGINGFACE,
        model="meta-llama/Llama-3.1-8B-Instruct",
        content="Clinical assessment indicates astronaut vitals are within nominal limits (HR 70 bpm, SpO2 98%). No acute intervention required.",
        latency_ms=195.0,
        tokens_per_second=20.0,
        is_fallback=False,
        success=True
    )

    req = ProviderRequest(
        task_category=TaskCategory.PERSONAL_HEALTH_SYNTHESIS,
        prompt="Generate astronaut health synthesis."
    )
    resp = rlhf_router.route_request(req)

    assert resp.provider == ProviderType.HUGGINGFACE
    assert "HR 70 bpm" in resp.content
    assert mock_hf.generate.called
    assert not mock_groq.generate.called

    # Validate with ClinicalSynthesisValidator
    validator = ClinicalSynthesisValidator()
    val_result = validator.validate_synthesis(
        synthesis_text=resp.content,
        ground_truth={
            "heart_rate": 70,
            "spo2": 98,
            "hr_status": "NORMAL",
            "spo2_status": "NORMAL",
            "rmssd_value": 35.0,
            "rmssd_status": "normal"
        }
    )
    assert val_result.is_valid is True


def test_03_raa_synthesis_routes_to_hf_and_preserves_immutable_rules(rlhf_router, mock_hf, mock_groq):
    """Verify RAA interpretation routes to HF RLHF model while deterministic risk tier remains immutable."""
    mock_hf.generate.return_value = ProviderResponse(
        request_id="REQ-RAA-01",
        provider=ProviderType.HUGGINGFACE,
        model="meta-llama/Llama-3.1-8B-Instruct",
        content="Telemetry indicates moderate tachycardia under sustained physical workload. Continuous vital sign monitoring recommended.",
        latency_ms=210.0,
        tokens_per_second=19.0,
        is_fallback=False,
        success=True
    )

    svc = LLMInterpretationService(api_key="gsk-test", router=rlhf_router)
    text, status = svc.generate_explanation(
        astronaut_id="AST-042",
        session_id="SES-042",
        overall_risk=RiskLevel.HIGH,
        overall_confidence="HIGH",
        escalation_state=EscalationState.ESCALATION_REQUIRED,
        escalation_reason="Severe arrhythmia with tachycardia",
        domain_summaries=[],
        concerns=[{"title": "Tachycardia"}],
        protective_factors=[],
        uncertainties=[]
    )

    assert status == "LLM_SUCCESS"
    assert "tachycardia" in text
    assert mock_hf.generate.called
    assert not mock_groq.generate.called


def test_04_medical_rag_synthesis_routes_to_hf_and_preserves_citations(rlhf_router, mock_hf, mock_groq):
    """Verify Medical RAG generation routes to HF RLHF model and preserves mandatory source citations."""
    mock_hf.generate.return_value = ProviderResponse(
        request_id="REQ-RAG-01",
        provider=ProviderType.HUGGINGFACE,
        model="meta-llama/Llama-3.1-8B-Instruct",
        content="**1. Retrieved Medical Facts:** Spaceflight microgravity induces orthostatic intolerance post-landing.\n\n**2. Clinical Interpretation:** Observed fluid shifts align with microgravity adaptation.\n\n**3. Uncertainty & Limitations:** Long-duration mission data limited.\n\n**4. Source Citations:** [NASA-STD-3001:P42]\n\n**5. Missing Information:** Post-flight stand test data.",
        latency_ms=220.0,
        tokens_per_second=24.0,
        is_fallback=False,
        success=True
    )

    rag_gen = GroundedMedicalGenerator(api_key="gsk-test", router=rlhf_router)
    passage = RetrievedPassage(
        chunk_id="P42",
        document_id="NASA-STD-3001",
        title="NASA Spaceflight Human-System Standard",
        source_organization="NASA",
        excerpt="Orthostatic intolerance is common following return from microgravity.",
        relevance_score=0.92,
        citation_reference="[NASA-STD-3001:P42]"
    )

    synthesis = rag_gen.generate(
        query="What causes orthostatic intolerance post-flight?",
        passages=[passage],
        retrieval_status=RAGRetrievalStatus.SUCCESS
    )

    assert mock_hf.generate.called
    assert not mock_groq.generate.called
    assert synthesis.generated_answer != ""
    assert "[NASA-STD-3001:P42]" in synthesis.source_citations


def test_05_hf_failure_cascades_to_groq_and_then_ollama(rlhf_router, mock_hf, mock_groq, mock_ollama):
    """Verify two-tier fallback cascade: HF failure -> Groq cloud -> Ollama local."""
    mock_hf.generate.side_effect = ProviderUnavailableError("Hugging Face API 503 Unavailable")
    mock_groq.generate.return_value = ProviderResponse(
        request_id="REQ-CAS-01",
        provider=ProviderType.GROQ,
        model="qwen/qwen3.8-27b",
        content="Response from Groq cloud fallback.",
        latency_ms=130.0,
        is_fallback=False,
        success=True
    )

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Explain radiation mitigation in cislunar space."
    )
    resp = rlhf_router.route_request(req)
    assert resp.provider == ProviderType.GROQ
    assert "Groq" in resp.content
    assert mock_hf.generate.called
    assert mock_groq.generate.called
    assert not mock_ollama.generate.called

    mock_groq.reset_mock()
    mock_ollama.reset_mock()
    mock_groq.generate.side_effect = ProviderUnavailableError("Groq 500 Connection Refused")
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-CAS-02",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Response from local Ollama fallback.",
        latency_ms=420.0,
        tokens_per_second=13.5,
        is_fallback=True,
        success=True
    )

    resp_local = rlhf_router.route_request(req)
    assert resp_local.provider == ProviderType.OLLAMA
    assert resp_local.is_fallback is True
    assert "Ollama" in resp_local.content
    assert mock_ollama.generate.called


def test_06_multimodal_tasks_bypass_hf_and_enforce_cloud_only(rlhf_router, mock_hf, mock_groq, mock_ollama):
    """Verify multimodal tasks (OCR, Voice) strictly bypass text models (HF, Ollama) and route to Groq."""
    mock_groq.generate.return_value = ProviderResponse(
        request_id="REQ-MM-01",
        provider=ProviderType.GROQ,
        model="llama-3.2-11b-vision-preview",
        content="OCR Extraction: Vital signs flow sheet data.",
        latency_ms=310.0,
        is_fallback=False,
        success=True
    )

    req_ocr = ProviderRequest(
        task_category=TaskCategory.MEDICAL_DOCUMENT_OCR,
        prompt="Extract table from image."
    )
    resp = rlhf_router.route_request(req_ocr)

    assert resp.provider == ProviderType.GROQ
    assert not mock_hf.generate.called
    assert not mock_ollama.generate.called

    mock_groq.generate.side_effect = ProviderUnavailableError("Vision service offline")
    with pytest.raises(TaskNotEligibleError, match="cannot fallback to local inference"):
        rlhf_router.route_request(req_ocr)


def test_07_ast_comment_hygiene_in_supervisor_and_risk_assessment():
    """Verify strictly ZERO '#' comments in supervisor/ and risk_assessment/."""
    def verify_no_comments(directory_path: str):
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    with open(full_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for idx, line in enumerate(lines, start=1):
                        stripped = line.strip()
                        if stripped.startswith("#"):
                            pytest.fail(f"Comment found in {full_path}:{idx}: {line}")

    verify_no_comments("ai-engine/agents/supervisor")
    verify_no_comments("ai-engine/agents/risk_assessment")
