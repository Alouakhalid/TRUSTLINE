"""Groq-exclusive speech-to-text service utilizing whisper-large-v3."""
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from groq import Groq
from ..config.settings import get_settings

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
MAX_AUDIO_BYTES = 25 * 1024 * 1024

class GroqVoiceTranscriptionError(Exception):
    """Custom exception raised when Groq speech processing fails."""
    pass

class NonGroqProviderDisallowedError(Exception):
    """Strict security guard preventing non-Groq speech recognition engines."""
    pass

class GroqVoiceService:
    """Voice transcription service strictly restricted to the official Groq API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        cfg = get_settings()
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = cfg.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        self.model = model or cfg.groq_whisper_model
        self._provider = "GROQ_EXCLUSIVE"
        self._client = Groq(api_key=self.api_key) if self.api_key else None

    def validate_audio_file(self, audio_path: Path) -> Path:
        """Verify audio file existence, supported format, and file size boundary."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

        ext = audio_path.suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio extension: {ext}. Allowed formats: {ALLOWED_AUDIO_EXTENSIONS}")

        file_size = audio_path.stat().st_size
        if file_size == 0:
            raise ValueError("Audio file is completely empty (0 bytes)")

        if file_size > MAX_AUDIO_BYTES:
            raise ValueError(f"Audio file exceeds Groq API limit of 25MB: {file_size} bytes")

        return audio_path

    def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """Transcribe speech file using Groq Whisper model."""
        if self._provider != "GROQ_EXCLUSIVE":
            raise NonGroqProviderDisallowedError("Strict policy violation: Non-Groq audio provider attempted.")

        path = Path(audio_file_path).resolve()
        self.validate_audio_file(path)

        if not self._client:
            raise GroqVoiceTranscriptionError("Groq API client is not configured (missing GROQ_API_KEY).")

        try:
            with open(path, "rb") as f:
                transcription = self._client.audio.transcriptions.create(
                    file=(path.name, f.read()),
                    model=self.model,
                    language=language,
                    prompt=prompt,
                    temperature=temperature,
                    response_format="verbose_json"
                )

            result_text = getattr(transcription, "text", "") or ""
            detected_lang = getattr(transcription, "language", language or "unknown")
            duration = getattr(transcription, "duration", None)

            return {
                "transcription_text": result_text.strip(),
                "detected_language": detected_lang,
                "duration_seconds": duration,
                "model_used": self.model,
                "provider": "groq",
                "status": "SUCCESS"
            }
        except Exception as exc:
            raise GroqVoiceTranscriptionError(f"Groq Whisper transcription failed: {str(exc)}") from exc

    def assert_no_non_groq_fallback(self, attempted_provider: str):
        """Security assertion confirming non-Groq fallback is completely prohibited."""
        if attempted_provider.lower() != "groq":
            raise NonGroqProviderDisallowedError(
                f"Unauthorized audio provider requested: '{attempted_provider}'. "
                f"TRUSTLINE architectural contract prohibits non-Groq speech engines."
            )
