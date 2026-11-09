"""Comprehensive unit test suite for Groq Vision OCR client, error handling, retries, and provider exclusivity."""
import json
import pytest
from unittest.mock import MagicMock, patch
from groq import APIError, RateLimitError, APITimeoutError

from ocr.schemas import ValidationStatus, ExtractionMethod
from ocr.groq_vision_client import (
    GroqVisionClient,
    GroqVisionAPIError,
    NonGroqProviderDisallowedError
)

def test_01_successful_vision_request():
    """Verify Groq Vision client correctly parses structured JSON response from vision model."""
    client = GroqVisionClient(api_key="gsk_mock_valid_key", model="qwen/qwen3.8-27b")

    mock_resp = MagicMock()
    mock_message = MagicMock(
        content=json.dumps({
            "records": [
                {
                    "test_name": "Hemoglobin",
                    "extracted_value": "15.1",
                    "original_unit": "g/dL",
                    "reference_range": "13.5-17.5",
                    "confidence": 0.97,
                    "is_ambiguous": False,
                    "warnings": []
                }
            ]
        })
    )
    mock_resp.choices = [MagicMock(message=mock_message)]

    with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
        records = client.extract_from_image_url(
            image_data_url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==",
            document_id="DOC-GROQ-001"
        )

    assert len(records) == 1
    assert records[0].test_name == "Hemoglobin"
    assert records[0].extracted_value == "15.1"
    assert records[0].original_unit == "g/dL"
    assert records[0].extraction_method == ExtractionMethod.GROQ_VISION_OCR
    assert records[0].extraction_confidence == 0.97

def test_02_invalid_api_key_handling():
    """Verify missing or invalid API key triggers explicit GroqVisionAPIError."""
    client = GroqVisionClient(api_key="", model="qwen/qwen3.8-27b")
    with pytest.raises(GroqVisionAPIError) as exc_info:
        client.extract_from_image_url(
            image_data_url="data:image/png;base64,mock",
            document_id="DOC-GROQ-002"
        )
    assert "not configured" in str(exc_info.value)

def test_03_model_unavailable_handling():
    """Verify unrecoverable Groq APIError raises GroqVisionAPIError without falling back to local OCR."""
    client = GroqVisionClient(api_key="gsk_mock_key")
    with patch.object(
        client._client.chat.completions,
        "create",
        side_effect=APIError(message="Model 'qwen/qwen3.8-27b' is not available", request=MagicMock(), body={})
    ):
        with pytest.raises(GroqVisionAPIError) as exc_info:
            client.extract_from_image_url(
                image_data_url="data:image/png;base64,mock",
                document_id="DOC-GROQ-003"
            )
        assert "extraction failed" in str(exc_info.value).lower()

def test_04_timeout_handling_and_retry():
    """Verify APITimeoutError triggers retry with exponential backoff before failing."""
    client = GroqVisionClient(api_key="gsk_mock_key", max_retries=2)
    with patch.object(
        client._client.chat.completions,
        "create",
        side_effect=APITimeoutError(request=MagicMock())
    ):
        with pytest.raises(GroqVisionAPIError):
            client.extract_from_image_url(
                image_data_url="data:image/png;base64,mock",
                document_id="DOC-GROQ-004"
            )

def test_05_rate_limit_handling():
    """Verify RateLimitError triggers exponential backoff retry."""
    client = GroqVisionClient(api_key="gsk_mock_key", max_retries=1)
    with patch.object(
        client._client.chat.completions,
        "create",
        side_effect=RateLimitError(message="Rate limit reached", response=MagicMock(status_code=429), body={})
    ):
        with pytest.raises(GroqVisionAPIError):
            client.extract_from_image_url(
                image_data_url="data:image/png;base64,mock",
                document_id="DOC-GROQ-005"
            )

def test_06_malformed_json_response_recovery():
    """Verify client handles markdown backticks and extracts embedded JSON from text response."""
    client = GroqVisionClient(api_key="gsk_mock_key")
    raw_markdown = (
        "Here is the medical extraction:\n```json\n"
        '{"records": [{"test_name": "Platelets", "extracted_value": "240", "original_unit": "10^3/uL"}]}\n'
        "```\nThank you."
    )
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=raw_markdown))]

    with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
        records = client.extract_from_image_url(
            image_data_url="data:image/png;base64,mock",
            document_id="DOC-GROQ-006"
        )
    assert len(records) == 1
    assert records[0].test_name == "Platelets"
    assert records[0].extracted_value == "240"

def test_07_missing_required_fields_handling():
    """Verify items lacking both test name and value are safely skipped without exception."""
    client = GroqVisionClient(api_key="gsk_mock_key")
    incomplete_json = json.dumps({
        "records": [
            {"test_name": "", "extracted_value": ""},
            {"test_name": "RBC", "extracted_value": "4.9", "original_unit": "10^6/uL"}
        ]
    })
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=incomplete_json))]

    with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
        records = client.extract_from_image_url(
            image_data_url="data:image/png;base64,mock",
            document_id="DOC-GROQ-007"
        )
    assert len(records) == 1
    assert records[0].test_name == "RBC"

def test_08_low_confidence_extraction_status():
    """Verify extraction confidence below 0.60 sets status to LOW_CONFIDENCE."""
    client = GroqVisionClient(api_key="gsk_mock_key")
    low_conf_json = json.dumps({
        "records": [
            {
                "test_name": "Glucose",
                "extracted_value": "99",
                "confidence": 0.45
            }
        ]
    })
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=low_conf_json))]

    with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
        records = client.extract_from_image_url(
            image_data_url="data:image/png;base64,mock",
            document_id="DOC-GROQ-008"
        )
    assert records[0].validation_status == ValidationStatus.LOW_CONFIDENCE
    assert any("Low vision" in w for w in records[0].validation_warnings)

def test_09_retry_behavior_eventual_success():
    """Verify transient error followed by success delivers valid extraction records."""
    client = GroqVisionClient(api_key="gsk_mock_key", max_retries=2)
    success_resp = MagicMock()
    mock_msg = MagicMock(
        content=json.dumps({
            "records": [{"test_name": "Sodium", "extracted_value": "141", "original_unit": "mEq/L"}]
        })
    )
    success_resp.choices = [MagicMock(message=mock_msg)]

    with patch.object(
        client._client.chat.completions,
        "create",
        side_effect=[RateLimitError("Transient 429", response=MagicMock(status_code=429), body={}), success_resp]
    ):
        records = client.extract_from_image_url(
            image_data_url="data:image/png;base64,mock",
            document_id="DOC-GROQ-009"
        )
    assert len(records) == 1
    assert records[0].test_name == "Sodium"

def test_10_strict_rejection_of_non_groq_fallback():
    """Verify requesting an unauthorized OCR provider strictly raises NonGroqProviderDisallowedError."""
    client = GroqVisionClient(api_key="gsk_mock_key")
    for unauthorized in ("tesseract", "paddleocr", "easyocr", "google_vision", "azure_ocr", "aws_textract"):
        with pytest.raises(NonGroqProviderDisallowedError):
            client._ensure_groq_exclusivity(unauthorized)
