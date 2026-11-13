"""
Unit tests for TRUSTLINE Hybrid AI Router (Priority 04).
Validates:
- Cloud routing (Groq healthy, timeout, rate limits, auth errors, connection failures)
- Local fallback routing (Ollama healthy, unavailable, both down)
- Circuit Breaker transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Task capability policies (LOCAL_ELIGIBLE, CLOUD_ONLY, DETERMINISTIC_OFFLINE, UNAVAILABLE)
- Telemetry recording, latency metrics, and API key masking
"""
import pytest
from unittest.mock import MagicMock, patch
from groq import APITimeoutError, RateLimitError, AuthenticationError, APIError

from hybrid_ai.schemas import (
    ProviderType,
    ProviderStatus,
    TaskCategory,
    RoutingPolicy,
    CircuitState,
    ProviderRequest,
    ProviderResponse,
    ProviderHealth,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    TaskNotEligibleError
)
from hybrid_ai.groq_provider import GroqProvider
from hybrid_ai.ollama_provider import OllamaProvider
from hybrid_ai.circuit_breaker import CircuitBreaker
from hybrid_ai.capability_registry import CapabilityRegistry
from hybrid_ai.telemetry import RouterTelemetry, RouterTelemetryRecord
from hybrid_ai.router import HybridAIRouter

@pytest.fixture
def mock_groq():
    provider = MagicMock(spec=GroqProvider)
    provider.provider_type = ProviderType.GROQ
    provider.default_model = "qwen/qwen3.8-27b"
    return provider

@pytest.fixture
def mock_ollama():
    provider = MagicMock(spec=OllamaProvider)
    provider.provider_type = ProviderType.OLLAMA
    provider.default_model = "qwen2.5:7b-instruct"
    return provider

@pytest.fixture
def circuit_breaker():
    return CircuitBreaker(failure_threshold=3, recovery_timeout=0.2, half_open_success_threshold=2)

@pytest.fixture
def router(mock_groq, mock_ollama, circuit_breaker):
    return HybridAIRouter(
        groq_provider=mock_groq,
        ollama_provider=mock_ollama,
        circuit_breaker=circuit_breaker,
        mode="HYBRID"
    )

def test_01_groq_healthy_selects_groq(router, mock_groq, mock_ollama):
    """When Groq is healthy, eligible requests route to Groq directly."""
    mock_groq.generate.return_value = ProviderResponse(
        request_id="REQ-001",
        provider=ProviderType.GROQ,
        model="qwen/qwen3.8-27b",
        content="Grounded clinical response from Groq.",
        latency_ms=120.0,
        is_fallback=False,
        success=True
    )
    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Explain microgravity cephalad fluid shift."
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.GROQ
    assert resp.is_fallback is False
    assert "Groq" in resp.content
    assert mock_groq.generate.called
    assert not mock_ollama.generate.called

def test_02_groq_timeout_falls_back_to_local_ollama(router, mock_groq, mock_ollama):
    """When Groq times out, eligible requests automatically fall back to Ollama."""
    mock_groq.generate.side_effect = ProviderTimeoutError("Groq request timed out")
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-002",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Local response from Qwen on Apple Silicon.",
        latency_ms=450.0,
        tokens_per_second=13.0,
        is_fallback=True,
        success=True
    )
    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Explain tachycardia."
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert resp.is_fallback is True
    assert "ProviderTimeoutError" in resp.fallback_reason
    assert mock_ollama.generate.called

def test_03_groq_connection_error_falls_back_to_local_ollama(router, mock_groq, mock_ollama):
    """When Groq suffers connection failure, eligible requests fall back to Ollama."""
    mock_groq.generate.side_effect = ProviderUnavailableError("Connection refused by DSN link")
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-003",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Local fallback successful.",
        latency_ms=300.0,
        is_fallback=True,
        success=True
    )
    req = ProviderRequest(
        task_category=TaskCategory.CONCISE_SUMMARIZATION,
        prompt="Summarize session."
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert resp.is_fallback is True

def test_04_groq_rate_limit_falls_back_to_local_ollama(router, mock_groq, mock_ollama):
    """When Groq hits HTTP 429 rate limit, fallback to local Ollama occurs immediately."""
    mock_groq.generate.side_effect = ProviderRateLimitError("Rate limit exceeded")
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-004",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Local response under rate limit.",
        latency_ms=250.0,
        is_fallback=True,
        success=True
    )
    req = ProviderRequest(
        task_category=TaskCategory.STRUCTURED_EXTRACTION,
        prompt="Extract vitals."
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert resp.is_fallback is True

def test_05_groq_auth_failure_does_not_endlessly_retry(mock_groq):
    """GroqProvider immediately raises AuthenticationError without wasteful retries."""
    with patch("hybrid_ai.groq_provider.Groq") as mock_groq_sdk:
        client_instance = MagicMock()
        mock_groq_sdk.return_value = client_instance
        client_instance.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API Key",
            response=MagicMock(status_code=401),
            body={"error": {"message": "Invalid API Key"}}
        )
        provider = GroqProvider(api_key="gsk_invalid", max_retries=3)
        req = ProviderRequest(task_category=TaskCategory.GENERAL_EXPLANATION, prompt="test")
        with pytest.raises(ProviderAuthenticationError):
            provider.generate(req)
        # Verify it was attempted only once (0 retries)
        assert client_instance.chat.completions.create.call_count == 1

def test_06_cloud_only_task_fails_without_local_fallback(router, mock_groq, mock_ollama):
    """Tasks designated CLOUD_ONLY (e.g. Vision OCR) refuse local fallback if cloud is down."""
    mock_groq.generate.side_effect = ProviderUnavailableError("Cloud offline")
    req = ProviderRequest(
        task_category=TaskCategory.MEDICAL_DOCUMENT_OCR,
        prompt="Extract scanned medical PDF."
    )
    with pytest.raises(TaskNotEligibleError) as exc_info:
        router.route_request(req)
    assert "cannot fallback to local inference" in str(exc_info.value)
    assert not mock_ollama.generate.called

def test_07_deterministic_offline_task_routes_deterministically(router, mock_groq, mock_ollama):
    """Tasks designated DETERMINISTIC_OFFLINE bypass LLMs entirely."""
    req = ProviderRequest(
        task_category=TaskCategory.SUPERVISOR_FINAL_REPORT,
        prompt="Generate supervisor briefing."
    )
    resp = router.route_request(req)
    assert resp.provider == ProviderType.DETERMINISTIC
    assert not mock_groq.generate.called
    assert not mock_ollama.generate.called

def test_08_unavailable_task_raises_error(router):
    """Tasks marked UNAVAILABLE are rejected explicitly."""
    req = ProviderRequest(
        task_category=TaskCategory.TOOL_CALLING,
        prompt="Call tool directly."
    )
    with pytest.raises(TaskNotEligibleError) as exc:
        router.route_request(req)
    assert "UNAVAILABLE" in str(exc.value)

def test_09_ollama_healthy_direct_execution(mock_ollama):
    """Ollama provider parses latency and calculates tokens per second."""
    provider = OllamaProvider(base_url="http://127.0.0.1:11434")
    sample_ollama_resp = {
        "response": '{"symptom": "headache"}',
        "total_duration": 4000000000,
        "load_duration": 10000000,
        "prompt_eval_duration": 500000000,
        "eval_duration": 3000000000,
        "eval_count": 39
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_ctx = MagicMock()
        mock_ctx.read.return_value = json_encode(sample_ollama_resp).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_ctx
        req = ProviderRequest(
            task_category=TaskCategory.STRUCTURED_EXTRACTION,
            prompt="Extract symptom",
            format_json=True
        )
        res = provider.generate(req)
        assert res.tokens_per_second == 13.0
        assert res.structured_data == {"symptom": "headache"}

def test_10_ollama_unavailable_raises_structured_failure(router, mock_groq, mock_ollama):
    """When both Groq and Ollama are unavailable, structured ProviderUnavailableError is raised."""
    mock_groq.generate.side_effect = ProviderUnavailableError("Groq 503")
    mock_ollama.generate.side_effect = ProviderUnavailableError("Ollama daemon down")
    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="test"
    )
    with pytest.raises(ProviderUnavailableError) as exc:
        router.route_request(req)
    assert "Both cloud" in str(exc.value)
    assert "and local" in str(exc.value)

def test_11_circuit_breaker_trips_to_open_after_failure_threshold(router, mock_groq, mock_ollama, circuit_breaker):
    """3 consecutive cloud failures trip the circuit breaker from CLOSED to OPEN."""
    mock_groq.generate.side_effect = ProviderUnavailableError("Network error")
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-CB",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Fallback response",
        success=True
    )
    req = ProviderRequest(task_category=TaskCategory.GENERAL_EXPLANATION, prompt="test")

    assert circuit_breaker.state == CircuitState.CLOSED
    router.route_request(req)
    assert circuit_breaker.consecutive_failures == 1
    assert circuit_breaker.state == CircuitState.CLOSED

    router.route_request(req)
    assert circuit_breaker.consecutive_failures == 2
    assert circuit_breaker.state == CircuitState.CLOSED

    router.route_request(req)
    assert circuit_breaker.consecutive_failures == 3
    assert circuit_breaker.state == CircuitState.OPEN

def test_12_circuit_breaker_open_avoids_unnecessary_cloud_requests(router, mock_groq, mock_ollama, circuit_breaker):
    """When circuit is OPEN, router immediately routes to Ollama without attempting Groq."""
    circuit_breaker.force_state(CircuitState.OPEN)
    circuit_breaker.recovery_timeout = 9999.0  # stay open
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-OPEN",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Fast fallback while cloud open",
        success=True
    )
    req = ProviderRequest(task_category=TaskCategory.GENERAL_EXPLANATION, prompt="test")
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert "Circuit breaker OPEN" in resp.fallback_reason
    assert not mock_groq.generate.called

def test_13_circuit_breaker_recovery_to_half_open_and_closed(circuit_breaker):
    """After recovery timeout, circuit enters HALF_OPEN; 2 successes return it to CLOSED."""
    import time
    circuit_breaker.force_state(CircuitState.OPEN)
    circuit_breaker.last_state_change = time.time() - 10.0
    circuit_breaker.recovery_timeout = 5.0

    # Next check enters HALF_OPEN
    assert circuit_breaker.can_attempt_cloud() is True
    assert circuit_breaker.state == CircuitState.HALF_OPEN

    # First canary success
    circuit_breaker.record_success()
    assert circuit_breaker.state == CircuitState.HALF_OPEN
    assert circuit_breaker.consecutive_successes == 1

    # Second canary success restores CLOSED
    circuit_breaker.record_success()
    assert circuit_breaker.state == CircuitState.CLOSED
    assert circuit_breaker.consecutive_successes == 0

def test_14_circuit_breaker_half_open_failure_re_trips_to_open(circuit_breaker):
    """If canary request fails in HALF_OPEN, circuit immediately re-trips to OPEN."""
    circuit_breaker.force_state(CircuitState.HALF_OPEN)
    circuit_breaker.record_failure(Exception("Canary probe failed"))
    assert circuit_breaker.state == CircuitState.OPEN

def test_15_telemetry_captures_fields_and_masks_secrets(router, mock_groq):
    """Telemetry records metadata, timing, and ensures no API keys leak."""
    mock_groq.generate.return_value = ProviderResponse(
        request_id="REQ-TEL",
        provider=ProviderType.GROQ,
        model="qwen/qwen3.8-27b",
        content="Telemetry test",
        latency_ms=88.5,
        success=True
    )
    req = ProviderRequest(
        task_category=TaskCategory.PERSONAL_HEALTH_SYNTHESIS,
        request_id="REQ-TEL",
        prompt="Synthesize briefing"
    )
    router.route_request(req)
    records = router.telemetry.get_records()
    assert len(records) > 0
    last_rec = records[-1]
    assert last_rec.request_id == "REQ-TEL"
    assert last_rec.provider_selected == "GROQ"
    assert last_rec.routing_decision == "CLOUD_DIRECT"
    assert "gsk_" not in str(last_rec.model_dump())

def test_16_local_only_mode_forces_local_execution(router, mock_groq, mock_ollama):
    """When router mode is LOCAL_ONLY, cloud is completely bypassed."""
    router.mode = "LOCAL_ONLY"
    mock_ollama.generate.return_value = ProviderResponse(
        request_id="REQ-LOCAL",
        provider=ProviderType.OLLAMA,
        model="qwen2.5:7b-instruct",
        content="Local only response",
        success=True
    )
    req = ProviderRequest(task_category=TaskCategory.GENERAL_EXPLANATION, prompt="test")
    resp = router.route_request(req)
    assert resp.provider == ProviderType.OLLAMA
    assert not mock_groq.generate.called
    assert "LOCAL_ONLY mode forced" in resp.fallback_reason

def json_encode(obj):
    import json
    return json.dumps(obj)
