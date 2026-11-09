"""Unit tests for Groq-exclusive speech-to-text service and non-Groq security guards."""
import os
import tempfile
from pathlib import Path
import pytest
from personal_health.services.groq_voice_service import (
    GroqVoiceService,
    NonGroqProviderDisallowedError,
    GroqVoiceTranscriptionError
)

def test_non_groq_fallback_strict_rejection():
    """Verify that attempting to route audio to any non-Groq provider raises strict security error."""
    svc = GroqVoiceService()
    for forbidden_provider in ["openai", "gemini", "azure", "google", "deepgram", "assemblyai", "browser"]:
        with pytest.raises(NonGroqProviderDisallowedError):
            svc.assert_no_non_groq_fallback(forbidden_provider)

def test_audio_file_validation_unsupported_format():
    """Reject unsupported audio file extensions."""
    svc = GroqVoiceService()
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
        with pytest.raises(ValueError, match="Unsupported audio extension"):
            svc.validate_audio_file(Path(tmp.name))

def test_audio_file_validation_empty_file():
    """Reject 0-byte audio files."""
    svc = GroqVoiceService()
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        with pytest.raises(ValueError, match="empty"):
            svc.validate_audio_file(Path(tmp.name))

def test_groq_voice_missing_key_behavior():
    """Verify clean error when Groq API key is absent."""
    svc = GroqVoiceService(api_key="")
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        tmp.write(b"RIFF....WAVEfmt ....data....")
        tmp.flush()
        with pytest.raises(GroqVoiceTranscriptionError, match="missing GROQ_API_KEY"):
            svc.transcribe_audio(tmp.name)
