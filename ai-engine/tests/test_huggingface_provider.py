"""
Unit tests for HuggingFaceProvider (Priority 05).

Validates:
- Initialization with defaults and custom parameters
- Configuration check based on API key / HF_TOKEN presence
- Successful generation and JSON mode via InferenceClient
- Error classification: 401 (Authentication), 429 (Rate Limit), Timeout, 500/Unavailable
- Exponential backoff retry logic
- Synchronous and asynchronous health check execution
"""

import pytest
from unittest.mock import MagicMock, patch
import json

from hybrid_ai.schemas import (
    ProviderType,
    ProviderStatus,
    ProviderRequest,
    ProviderResponse,
    ProviderHealth,
    TaskCategory,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError
)
from hybrid_ai.huggingface_provider import HuggingFaceProvider


@pytest.fixture
def unconfigured_provider():
    with patch.dict("os.environ", {}, clear=True):
        return HuggingFaceProvider(api_key="")


@pytest.fixture
def mock_hf_provider():
    with patch.dict("os.environ", {"HF_TOKEN": "hf_test_mock_token_12345"}):
        provider = HuggingFaceProvider(
            api_key="hf_test_mock_token_12345",
            model="meta-llama/Llama-3.1-8B-Instruct",
            max_retries=2
        )
        provider._client = MagicMock()
        return provider


def test_init_default_and_custom_configuration():
    """Verify default parameters and custom overrides during initialization."""
    with patch.dict("os.environ", {}, clear=True):
        p_default = HuggingFaceProvider(api_key="hf_custom_key")
        assert p_default.default_model == "meta-llama/Llama-3.1-8B-Instruct"
        assert p_default.provider == "auto"
        assert p_default.default_timeout == 25.0
        assert p_default.max_retries == 2
        assert p_default.is_configured() is True

    p_custom = HuggingFaceProvider(
        api_key="hf_custom_key",
        model="Qwen/Qwen2.5-72B-Instruct",
        provider="together",
        timeout=15.0,
        max_retries=1
    )
    assert p_custom.default_model == "Qwen/Qwen2.5-72B-Instruct"
    assert p_custom.provider == "together"
    assert p_custom.default_timeout == 15.0
    assert p_custom.max_retries == 1


def test_is_configured_behavior(unconfigured_provider):
    """Verify is_configured returns False when token is missing and True when provided."""
    assert unconfigured_provider.is_configured() is False

    with patch.dict("os.environ", {"HF_TOKEN": "hf_dummy_token"}):
        p_env = HuggingFaceProvider()
        assert p_env.is_configured() is True


def test_generate_unconfigured_raises_unavailable(unconfigured_provider):
    """Calling generate on an unconfigured provider raises ProviderUnavailableError."""
    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Synthesize baseline vitals."
    )
    with pytest.raises(ProviderUnavailableError, match="missing HF_TOKEN"):
        unconfigured_provider.generate(req)


def test_generate_successful_completion(mock_hf_provider):
    """Verify successful generation parses choices, usage, and returns structured ProviderResponse."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Grounded synthesis of astronaut vitals: HR 72 bpm, SpO2 99%."
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 35
    mock_usage.completion_tokens = 20

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_hf_provider._client.chat_completion.return_value = mock_response

    req = ProviderRequest(
        task_category=TaskCategory.PERSONAL_HEALTH_SYNTHESIS,
        prompt="Analyze heart rate telemetry.",
        system_prompt="You are a clinical decision support system."
    )

    resp = mock_hf_provider.generate(req)
    assert resp.success is True
    assert resp.provider == ProviderType.HUGGINGFACE
    assert resp.model == "meta-llama/Llama-3.1-8B-Instruct"
    assert "HR 72 bpm" in resp.content
    assert resp.latency_ms > 0
    assert resp.tokens_per_second is not None
    assert resp.metadata["prompt_tokens"] == 35
    assert resp.metadata["completion_tokens"] == 20


def test_generate_with_json_formatting(mock_hf_provider):
    """Verify JSON mode request adds prompt formatting and parses structured data."""
    json_payload = {"risk_tier": "LOW", "confidence": 0.98, "recommendation": "Maintain standard monitoring."}
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(json_payload)
    mock_usage = MagicMock(prompt_tokens=40, completion_tokens=25)

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_hf_provider._client.chat_completion.return_value = mock_response

    req = ProviderRequest(
        task_category=TaskCategory.AGENT_REPORT_FORMATTING,
        prompt="Assess crew status.",
        format_json=True
    )

    resp = mock_hf_provider.generate(req)
    assert resp.success is True
    assert resp.structured_data == json_payload
    called_kwargs = mock_hf_provider._client.chat_completion.call_args.kwargs
    assert called_kwargs["response_format"] == {"type": "json_object"}


@patch("time.sleep")
def test_generate_rate_limit_backoff_and_raises(mock_sleep, mock_hf_provider):
    """Verify 429 rate limit triggers exponential backoff retries and raises ProviderRateLimitError."""
    mock_hf_provider._client.chat_completion.side_effect = Exception("HTTP 429: Too Many Requests / Rate limit exceeded")

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Test rate limit handling."
    )

    with pytest.raises(ProviderRateLimitError, match="rate limit exceeded"):
        mock_hf_provider.generate(req)

    assert mock_hf_provider._client.chat_completion.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1.0)
    mock_sleep.assert_any_call(2.0)


def test_generate_auth_failure_raises_authentication_error(mock_hf_provider):
    """Verify 401 unauthorized raises ProviderAuthenticationError without retrying."""
    mock_hf_provider._client.chat_completion.side_effect = Exception("HTTP 401 Client Error: Unauthorized for url")

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Test auth failure."
    )

    with pytest.raises(ProviderAuthenticationError, match="Authentication failed"):
        mock_hf_provider.generate(req)

    assert mock_hf_provider._client.chat_completion.call_count == 1


@patch("time.sleep")
def test_generate_timeout_backoff_and_raises(mock_sleep, mock_hf_provider):
    """Verify timeout triggers retries and raises ProviderTimeoutError."""
    mock_hf_provider._client.chat_completion.side_effect = Exception("Read timed out. (read timeout=25.0)")

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Test timeout handling.",
        timeout_seconds=5.0
    )

    with pytest.raises(ProviderTimeoutError, match="timed out"):
        mock_hf_provider.generate(req)

    assert mock_hf_provider._client.chat_completion.call_count == 3
    assert mock_sleep.call_count == 2


@patch("time.sleep")
def test_generate_unavailable_after_generic_error_retries(mock_sleep, mock_hf_provider):
    """Verify generic API errors retry and then raise ProviderUnavailableError."""
    mock_hf_provider._client.chat_completion.side_effect = Exception("503 Service Unavailable: Backend overloaded")

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Test generic 503."
    )

    with pytest.raises(ProviderUnavailableError, match="Hugging Face provider error"):
        mock_hf_provider.generate(req)

    assert mock_hf_provider._client.chat_completion.call_count == 3


def test_health_check_unconfigured(unconfigured_provider):
    """Health check on unconfigured provider returns UNAVAILABLE status."""
    health = unconfigured_provider.health_check()
    assert health.status == ProviderStatus.UNAVAILABLE
    assert health.provider == ProviderType.HUGGINGFACE
    assert "HF_TOKEN not configured" in (health.error or "")


def test_health_check_healthy(mock_hf_provider):
    """Health check returns HEALTHY when endpoint probe succeeds."""
    mock_hf_provider._client.get_endpoint_info.return_value = {"status": "ok"}

    health = mock_hf_provider.health_check()
    assert health.status == ProviderStatus.HEALTHY
    assert health.provider == ProviderType.HUGGINGFACE
    assert health.latency_ms is not None
    assert health.details["configured"] is True
    assert health.details["model"] == "meta-llama/Llama-3.1-8B-Instruct"


def test_health_check_auth_error(mock_hf_provider):
    """Health check returns UNAVAILABLE on 401 unauthorized probe."""
    mock_hf_provider._client.get_endpoint_info.side_effect = Exception("401 Unauthorized")

    health = mock_hf_provider.health_check()
    assert health.status == ProviderStatus.UNAVAILABLE
    assert "Authentication failure" in (health.error or "")


@pytest.mark.asyncio
async def test_generate_async_and_health_check_async(mock_hf_provider):
    """Verify async wrappers execute correctly."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Async response test."
    mock_response = MagicMock(choices=[mock_choice], usage=None)
    mock_hf_provider._client.chat_completion.return_value = mock_response

    req = ProviderRequest(
        task_category=TaskCategory.GENERAL_EXPLANATION,
        prompt="Async prompt"
    )

    resp = await mock_hf_provider.generate_async(req)
    assert resp.success is True
    assert resp.content == "Async response test."

    mock_hf_provider._client.get_endpoint_info.return_value = {"status": "ok"}
    health = await mock_hf_provider.health_check_async()
    assert health.status == ProviderStatus.HEALTHY
